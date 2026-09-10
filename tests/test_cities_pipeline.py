"""Client und Pipeline — gegen einen gemockten Server.

Der wichtigste Test hier ist ``test_session_setzt_den_zeitfilter_auf_jeder_seite``:
Er hält den Fehler fest, der im Probelauf 6.000 Papiere aus dem falschen
Jahrzehnt geholt hat, ohne dass irgendetwas rot geworden wäre.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests
import responses

from council.cities.adapters.allris4 import _seiten_rueckwaerts
from council.cities.adapters.session import _seiten_vorwaerts
from council.cities.oparl import OParlClient
from council.cities.pipeline import (PROTOCOL_NIETEN, _hole, extract, normalize,
                                     protokoll_fenster, raw_path_for)
from council.cities.registry import BodySpec
from council.cities.store import CitiesStore
from council.cities.text import EXTRACTOR, VERSION

FIXTURES = Path(__file__).parent / "fixtures" / "cities"


@pytest.fixture()
def client(tmp_path):
    store = CitiesStore(tmp_path / "raw.sqlite")
    c = OParlClient(store, "teststadt", tmp_path / "files")
    yield c
    store.close()


@pytest.fixture(autouse=True)
def ohne_wartezeit(monkeypatch):
    """Die Drosselung ist im Betrieb richtig und im Test nur Wartezeit."""
    monkeypatch.setattr("council.cities.oparl.throttle", lambda url, gap=1.0: None)


# --------------------------------------------------------------------- Client

@responses.activate
def test_get_json_legt_die_antwort_roh_ab(client):
    responses.add(responses.GET, "https://x.de/oparl/system",
                  json={"id": "https://x.de/oparl/system", "oparlVersion": "1.1"})
    daten = client.get_json("https://x.de/oparl/system", kind="system")
    assert daten["oparlVersion"] == "1.1"
    assert client.raw.latest_raw("https://x.de/oparl/system")["oparlVersion"] == "1.1"


@responses.activate
def test_get_json_wiederholt_nur_voruebergehende_fehler(client):
    responses.add(responses.GET, "https://x.de/a", status=503)
    responses.add(responses.GET, "https://x.de/a", json={"id": "https://x.de/a", "ok": True})
    assert client.get_json("https://x.de/a")["ok"] is True
    assert len(responses.calls) == 2

    # Ein 404 ist eine Aussage des Servers — den zu wiederholen kostet nur Zeit.
    responses.add(responses.GET, "https://x.de/b", status=404)
    with pytest.raises(requests.HTTPError):
        client.get_json("https://x.de/b")
    assert len([c for c in responses.calls if c.request.url.endswith("/b")]) == 1


@responses.activate
def test_get_file_ist_bei_404_kein_laufabbruch(client):
    """Magdeburgs Schnittstelle nennt Adressen, die es nicht gibt."""
    responses.add(responses.GET, "https://x.de/doc/1", status=404)
    assert client.get_file("https://x.de/doc/1") is None


@responses.activate
def test_store_file_legt_nach_inhalt_ab_und_dedupliziert(client, tmp_path):
    responses.add(responses.GET, "https://x.de/doc/1", body=b"%PDF-1.4 abc",
                  content_type="application/pdf")
    daten, mime = client.get_file("https://x.de/doc/1")
    sha = client.store_file(daten, mime)
    pfad = tmp_path / "files" / sha[:2] / f"{sha}.pdf"
    assert pfad.read_bytes() == b"%PDF-1.4 abc"
    assert client.raw.raw_file(sha)["bytes"] == 12
    # Dieselben Bytes an einem zweiten Papier: eine Datei, ein Eintrag.
    assert client.store_file(daten, mime) == sha
    assert len(client.raw.raw_files()) == 1


# ------------------------------------------------------- Blättern je Dialekt

def _liste(objekte, seite, gesamt, url="https://x.de/papers"):
    return {
        "data": objekte,
        "pagination": {"elementsPerPage": 10, "currentPage": seite, "totalPages": gesamt},
        "links": {"first": f"{url}?page=1&size=10", "self": f"{url}?page={seite}&size=10",
                  "last": f"{url}?page={gesamt}&size=10"},
    }


@responses.activate
def test_allris_blaettert_rueckwaerts_und_haelt_bei_alten_an(client):
    """Die neuesten Objekte stehen auf der LETZTEN Seite (gemessen: 1.955 von 1.955)."""
    # 50 Seiten Bestand, aber nur die letzten sechs liegen im Zeitfenster —
    # so sieht ein echter Jahrgang neben zehn Altjahrgängen aus.
    def antwort(request):
        seite = int(parse_qs(urlparse(request.url).query).get("page", ["1"])[0])
        datum = "2026-09-01" if seite >= 45 else "2019-01-01"
        objekte = [{"id": f"https://x.de/p/{seite}-{i}", "name": "T", "date": datum}
                   for i in range(10)]
        return 200, {"Content-Type": "application/json"}, json.dumps(_liste(objekte, seite, 50))

    responses.add_callback(responses.GET, "https://x.de/papers", callback=antwort)
    geholt = list(_seiten_rueckwaerts(client, "https://x.de/papers", "paper", "2025-01-01"))

    seiten = [int(parse_qs(urlparse(c.request.url).query).get("page", ["1"])[0])
              for c in responses.calls]
    assert seiten[0] == 1, "erst die erste Seite, um `links.last` zu lernen"
    assert seiten[1:4] == [50, 49, 48], "danach von hinten"
    # Alles Neue ist dabei …
    assert len([o for o in geholt if o["date"] == "2026-09-01"]) == 60
    # … aber der Altbestand wird nicht durchblättert: nach 80 alten ist Schluss.
    assert len(responses.calls) <= 17, "sonst läuft der Lauf bis zum Anfang"


@responses.activate
def test_allris_zaehlt_undatierte_papiere_als_alt(client):
    """Osnabrücks Altbestand trägt kein ``date``.

    Wer „unbekannt" als „vielleicht neu" liest, blättert bis 1997 zurück —
    im Probelauf lief der Faden deshalb zehn Minuten statt einer.
    """
    def antwort(request):
        seite = int(parse_qs(urlparse(request.url).query).get("page", ["1"])[0])
        objekte = [{"id": f"https://x.de/p/{seite}-{i}", "name": "T"} for i in range(10)]
        return 200, {"Content-Type": "application/json"}, json.dumps(_liste(objekte, seite, 50))

    responses.add_callback(responses.GET, "https://x.de/papers", callback=antwort)
    list(_seiten_rueckwaerts(client, "https://x.de/papers", "paper", "2025-01-01"))
    # 80 alte Objekte = 8 Seiten, plus die erste zum Lernen von `last`.
    assert len(responses.calls) <= 11


@responses.activate
def test_session_setzt_den_zeitfilter_auf_jeder_seite(client):
    """Der ``next``-Link verliert ``created_since`` ab Seite 3.

    Im Probelauf hat das Münster 6.000 Papiere beschert, von denen 376 ins
    Zeitfenster fielen — ohne Fehlermeldung, ohne Auffälligkeit. Deshalb wird
    ``page=N`` samt Filter selbst gesetzt und ``links.next`` nie gefolgt.
    """
    def antwort(request):
        query = parse_qs(urlparse(request.url).query)
        seite = int(query.get("page", ["1"])[0])
        objekte = [{"id": f"https://x.de/p/{seite}-{i}"} for i in range(100 if seite < 3 else 5)]
        return 200, {"Content-Type": "application/json"}, json.dumps({
            "data": objekte,
            # Der Server bietet ab Seite 2 einen Folge-Link OHNE Filter an.
            "links": {"next": f"https://x.de/papers?page={seite + 1}&limit=100"},
        })

    responses.add_callback(responses.GET, "https://x.de/papers", callback=antwort)
    list(_seiten_vorwaerts(client, "https://x.de/papers", "2025-09-01"))

    assert len(responses.calls) == 3, "bis zur ersten unvollen Seite"
    for anruf in responses.calls:
        query = parse_qs(urlparse(anruf.request.url).query)
        assert "created_since" in query, f"Filter fehlt: {anruf.request.url}"
        assert query["created_since"][0].startswith("2025-09-01")


# ------------------------------------------------------------------ Pipeline

def _rohdatei_mit_papieren(raw_dir: Path, stadt: str) -> None:
    store = CitiesStore(raw_path_for(raw_dir, stadt))
    for papier in json.loads((FIXTURES / f"{stadt}_papers.json").read_text(encoding="utf-8")):
        store.put_raw_object(stadt, "paper", papier["id"], papier)
    store.close()


def test_normalize_ist_idempotent(tmp_path):
    """Zweimal laufen lassen ändert nichts — die Stufe wird oft wiederholt.

    **`last_fetched` gehört NICHT dazu**, und das ist keine Bequemlichkeit:
    Der Wert sagt, wann zuletzt geholt wurde, und der zweite Lauf ist ein
    zweiter Lauf. Bis 09.09.2026 verglich der Test ihn mit, und die Prüfung
    fiel um, wann immer die beiden Aufrufe eine Sekundengrenze überschritten
    — in der CI unter Last regelmäßig, lokal so gut wie nie. Ein Test, der
    einmal in zwanzig Läufen ohne Ursache rot wird, bringt niemandem etwas
    bei; er lehrt nur, rote Läufe noch einmal zu starten.
    """
    spec = BodySpec("osnabrueck", "Osnabrück", "NI", "allris4", "https://x.de/oparl/system")
    _rohdatei_mit_papieren(tmp_path / "raw", "osnabrueck")
    main = CitiesStore(tmp_path / "cities.sqlite")

    def ohne_zeitstempel(zeilen):
        return [{k: v for k, v in z.items() if k != "last_fetched"} for z in zeilen]

    try:
        erst = normalize(spec, tmp_path / "raw", main)
        stand = ohne_zeitstempel(main.stats())
        zweit = normalize(spec, tmp_path / "raw", main)
        assert erst == zweit
        assert ohne_zeitstempel(main.stats()) == stand
        assert main.paper_count("osnabrueck") == 4
    finally:
        main.close()


def test_normalize_ohne_rohdatei_ist_kein_fehler(tmp_path):
    """Eine Stadt, die noch nie geerntet wurde, darf den Lauf nicht abbrechen."""
    spec = BodySpec("muenster", "Münster", "NW", "session", "https://x.de/oparl/system")
    main = CitiesStore(tmp_path / "cities.sqlite")
    try:
        assert normalize(spec, tmp_path / "leer", main)["papers"] == 0
    finally:
        main.close()


def test_extract_macht_aus_bytes_text(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    schreiber = pypdf.PdfWriter()
    schreiber.add_blank_page(width=200, height=200)
    ziel = tmp_path / "leer.pdf"
    with open(ziel, "wb") as f:
        schreiber.write(f)
    daten = ziel.read_bytes()

    from council.cities.model import Batch, File, FileRole
    from council.cities.oparl import file_path
    import hashlib

    sha = hashlib.sha256(daten).hexdigest()
    pfad = file_path(tmp_path / "files", sha)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(daten)

    main = CitiesStore(tmp_path / "cities.sqlite")
    try:
        main.upsert_batch(Batch(files=[File("f1", "x", FileRole.MAIN, sha256=sha)]))
        zahlen = extract(main, tmp_path / "files")
        # Eine leere Seite hat keine Textebene — genau dafür gibt es „empty".
        assert zahlen["empty"] == 1
        assert main.text_for_file("f1", EXTRACTOR, VERSION) == ""
        # Zweiter Lauf findet nichts mehr zu tun.
        assert extract(main, tmp_path / "files") == {
            "ok": 0, "thin": 0, "empty": 0, "error": 0, "missing_bytes": 0}
    finally:
        main.close()


def test_extract_meldet_fehlende_bytes_statt_zu_scheitern(tmp_path):
    from council.cities.model import Batch, File, FileRole

    main = CitiesStore(tmp_path / "cities.sqlite")
    try:
        main.upsert_batch(Batch(files=[File("f1", "x", FileRole.MAIN, sha256="0" * 64)]))
        assert extract(main, tmp_path / "files")["missing_bytes"] == 1
    finally:
        main.close()


# ------------------------------------------------------ Niederschriften (PR 31)

def _sitzung_mit_protokoll(store: CitiesStore, stadt: str, kennung: str,
                           start: str | None, url: str) -> None:
    """Eine Sitzung samt Niederschrift, wie sie nach dem Normalisieren dasteht."""
    from council.cities.model import Batch, File, FileRole, Meeting
    store.upsert_batch(Batch(
        meetings=[Meeting(kennung, stadt, None, "Sitzung", start)],
        files=[File(f"{kennung}-prot", stadt, FileRole.PROTOCOL,
                    meeting_id=kennung, access_url=url)]))


def test_protokoll_fenster_rechnet_monate_zurueck():
    from datetime import date
    assert protokoll_fenster(24, date(2026, 9, 10)) == "2024-09-01"
    assert protokoll_fenster(24, date(2026, 1, 5)) == "2024-01-01"
    # Über die Jahresgrenze in die andere Richtung: Januar minus 2 Monate.
    assert protokoll_fenster(2, date(2026, 1, 31)) == "2025-11-01"


def test_alte_sitzungen_bleiben_liegen(tmp_path):
    """Potsdam führt 663 Niederschriften; die Karte reicht keine zehn Jahre zurück."""
    store = CitiesStore(tmp_path / "raw.sqlite")
    try:
        _sitzung_mit_protokoll(store, "potsdam", "m-neu", "2026-05-05", "https://x.de/p/neu")
        _sitzung_mit_protokoll(store, "potsdam", "m-alt", "2019-05-05", "https://x.de/p/alt")
        _sitzung_mit_protokoll(store, "potsdam", "m-ohne", None, "https://x.de/p/ohne")

        offen = store.files_without_bytes("potsdam", ("protocol",), meeting_since="2024-09-01")
        assert [d["id"] for d in offen] == ["m-neu-prot"]
        # Ohne Fenster ist alles dabei — der Vorlagen-Pfad bleibt unberührt.
        assert len(store.files_without_bytes("potsdam", ("protocol",))) == 3
    finally:
        store.close()


@responses.activate
def test_drei_nieten_beenden_die_protokolle_einer_stadt(client, tmp_path):
    """Magdeburg nennt 606 Adressen, die alle mit 404 antworten.

    Ohne Abbruch wären das 606 sinnlose Abrufe bei einer Stadt, die uns nichts
    getan hat — und der Lauf sähe dabei völlig gesund aus.
    """
    for i in range(10):
        responses.add(responses.GET, f"https://x.de/prot/{i}", status=404)
    offen = [{"id": f"f{i}", "access_url": f"https://x.de/prot/{i}"} for i in range(10)]
    zahlen = {"protocols_fetched": 0, "protocols_failed": 0}

    _hole(client, client.raw, "magdeburg", offen, zahlen, "Niederschriften",
          nieten_max=PROTOCOL_NIETEN,
          schluessel=("protocols_fetched", "protocols_failed"))

    assert zahlen["protocols_failed"] == PROTOCOL_NIETEN
    assert len(responses.calls) == PROTOCOL_NIETEN


@responses.activate
def test_eine_niete_zwischendrin_beendet_nichts(client):
    """Nur FOLGENDE Fehlschläge zählen — eine kaputte Datei ist kein Ausfall."""
    responses.add(responses.GET, "https://x.de/prot/0", status=404)
    for i in (1, 2, 3):
        responses.add(responses.GET, f"https://x.de/prot/{i}", body=b"%PDF-1.4 x",
                      content_type="application/pdf")
    offen = [{"id": f"f{i}", "access_url": f"https://x.de/prot/{i}"} for i in range(4)]
    zahlen = {"protocols_fetched": 0, "protocols_failed": 0}

    _hole(client, client.raw, "muenster", offen, zahlen, "Niederschriften",
          nieten_max=PROTOCOL_NIETEN,
          schluessel=("protocols_fetched", "protocols_failed"))

    assert (zahlen["protocols_fetched"], zahlen["protocols_failed"]) == (3, 1)


def test_stats_zaehlt_protokolle_und_ihren_text(tmp_path):
    """Ohne diese Zahl merkt niemand, dass eine Stadt nur Adressen liefert."""
    from council.cities.model import Body
    main = CitiesStore(tmp_path / "cities.sqlite")
    try:
        main.upsert_body(Body("muenster", "Münster", "NW", "session"))
        _sitzung_mit_protokoll(main, "muenster", "m1", "2026-05-05", "https://x.de/p/1")
        _sitzung_mit_protokoll(main, "muenster", "m2", "2026-05-06", "https://x.de/p/2")
        main.put_text("m1-prot", EXTRACTOR, VERSION, "Punkt 1 der Tagesordnung …", 4, "ok")
        main.put_text("m2-prot", EXTRACTOR, VERSION, "", 0, "empty")

        zeile = next(z for z in main.stats() if z["id"] == "muenster")
        assert (zeile["protocols"], zeile["protocols_with_text"]) == (2, 1)
    finally:
        main.close()
