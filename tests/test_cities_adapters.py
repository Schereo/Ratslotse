"""Die Dialekte — gegen echte Rohobjekte aus fünf Ratsinformationssystemen.

Die Fixtures unter ``tests/fixtures/cities/`` sind gekürzte, aber
unveränderte Antworten der Schnittstellen (geholt am 07.09.2026). Sie sind
der Grund, warum diese Tests etwas beweisen: Ein selbstgebautes Beispiel
hätte genau die Eigenheiten nicht, an denen der Probelauf gescheitert ist.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from council.cities.adapters import get_adapter
from council.cities.adapters._common import (
    link_by_title, normalize_title, parse_date, promote_main,
)
from council.cities.adapters.session import _magdeburg_url, url_fix_for
from council.cities.model import (
    AgendaItem, Batch, Consultation, File, FileRole, Meeting, Outcome, Paper, PaperKind,
)
from council.cities.store import CitiesStore

FIXTURES = Path(__file__).parent / "fixtures" / "cities"
STAEDTE = {
    "osnabrueck": "allris4",
    "braunschweig": "allris4",
    "potsdam": "allris4",
    "muenster": "session",
    "magdeburg": "session",
}


def lade(store: CitiesStore, stadt: str) -> None:
    for papier in json.loads((FIXTURES / f"{stadt}_papers.json").read_text(encoding="utf-8")):
        store.put_raw_object(stadt, "paper", papier["id"], papier)


@pytest.fixture()
def store(tmp_path):
    s = CitiesStore(tmp_path / "raw.sqlite")
    yield s
    s.close()


@pytest.mark.parametrize("stadt,dialekt", sorted(STAEDTE.items()))
def test_normalize_baut_papiere_mit_datei_und_beratung(store, stadt, dialekt):
    lade(store, stadt)
    batch = get_adapter(dialekt).normalize(stadt, store)

    assert len(batch.papers) == 4, "jedes Rohpapier wird zu genau einem Papier"
    for p in batch.papers:
        assert p.body_id == stadt
        assert p.name, "ein Papier ohne Titel wäre in jeder Liste unsichtbar"
        assert p.kind in set(PaperKind), p.kind
        assert p.id.startswith("http"), "die OParl-Kennung ist die Objekt-URL"

    # Jedes Papier bringt ein Hauptdokument mit — bei ALLRIS als mainFile,
    # bei Somacos als Anlage mit sprechendem Namen.
    haupt = [f for f in batch.files if f.role == FileRole.MAIN]
    assert len(haupt) == 4, f"{stadt}: Hauptdokumente nicht erkannt"
    for f in haupt:
        assert f.access_url and f.access_url.startswith("http")
        assert f.paper_id

    assert batch.consultations, f"{stadt}: keine Beratungsfolge"


def test_session_kennt_kein_mainfile(store):
    """Somacos hängt das Hauptdokument unter ``auxiliaryFile`` — nur der Name
    unterscheidet es von einem Lageplan."""
    lade(store, "muenster")
    roh = json.loads((FIXTURES / "muenster_papers.json").read_text(encoding="utf-8"))
    assert all("mainFile" not in p for p in roh)
    batch = get_adapter("session").normalize("muenster", store)
    haupt = [f for f in batch.files if f.role == FileRole.MAIN]
    # Je Papier genau eines — und es heißt „…vorlage", auch wenn es zwischen
    # sechs Anlagen an sechster Stelle steht.
    assert len(haupt) == 4
    assert {f.name for f in haupt} == {"Beschlussvorlage", "Berichtsvorlage"}
    assert len({f.paper_id for f in haupt}) == 4


def test_ohne_erkennbares_hauptdokument_gilt_die_erste_anlage(store):
    """Sonst bekäme ein Papier, dessen Anlagen alle „Anlage 1" heißen, nie Text."""
    nur_anlagen = [File("f1", "x", FileRole.AUXILIARY, name="Anlage 1"),
                   File("f2", "x", FileRole.AUXILIARY, name="Anlage 2")]
    assert [f.role for f in promote_main(nur_anlagen)] == [FileRole.MAIN, FileRole.AUXILIARY]
    # Wo eines erkannt ist, bleibt alles, wie es ist.
    mit_haupt = [File("f1", "x", FileRole.AUXILIARY, name="Anlage 1"),
                 File("f2", "x", FileRole.MAIN, name="Beschlussvorlage")]
    assert [f.role for f in promote_main(mit_haupt)] == [FileRole.AUXILIARY, FileRole.MAIN]
    assert promote_main([]) == []


def test_magdeburg_datei_adresse_wird_umgeschrieben(store):
    """Die Schnittstelle nennt Adressen, die durchweg 404 antworten.

    Gemessen an fünf Dokumenten am 07.09.2026: sowohl ``accessUrl`` als auch
    ``downloadUrl``. Dieselben Dateien liegen unter ``getfile.asp``.
    """
    lade(store, "magdeburg")
    batch = get_adapter("session").normalize("magdeburg", store)
    haupt = [f for f in batch.files if f.role == FileRole.MAIN]
    assert haupt, "Magdeburg hat Hauptdokumente"
    for f in haupt:
        assert "getfile.asp?id=" in (f.access_url or ""), f.access_url
        assert "downloadfiles" not in (f.access_url or "")
        assert "type=do" in (f.access_url or "")


def test_magdeburg_url_baut_die_kennung_ohne_fuehrende_nullen():
    datei = {"fileName": "00692749.pdf",
             "accessUrl": "https://ratsinfo.magdeburg.de/oparl/bodies/0001/downloadfiles/a/00692749.pdf"}
    assert _magdeburg_url(datei, datei["accessUrl"]) == \
        "https://ratsinfo.magdeburg.de/getfile.asp?id=692749&type=do"
    # Ohne erkennbare Nummer bleibt die Adresse, wie sie war.
    assert _magdeburg_url({"fileName": "anlage.pdf"}, "https://x/y") == "https://x/y"


def test_url_fix_greift_nur_bei_magdeburg():
    assert url_fix_for({"id": "https://ratsinfo.magdeburg.de/oparl/bodies/0001"}) is not None
    assert url_fix_for({"id": "https://oparl.stadt-muenster.de/bodies/0001"}) is None


def test_allris_leerdatum_gilt_als_unbekannt():
    """ALLRIS setzt ``created``/``modified`` bei jedem Objekt auf 2000-01-01.

    Wer den Wert für echt hält, sortiert den ganzen Bestand auf einen Tag —
    und ein Zeitfilter darauf liefert entweder alles oder nichts.
    """
    assert parse_date("2000-01-01T00:00:00+01:00") is None
    assert parse_date("2026-09-03") == "2026-09-03"
    assert parse_date(None) is None
    assert parse_date("kein Datum") is None


def test_allris_verbindet_papier_und_ergebnis_ueber_den_titel(store):
    """ALLRIS nennt in der Beratungsfolge keinen Tagesordnungspunkt.

    Ohne den Titelabgleich hätte in Osnabrück, Braunschweig und Potsdam
    **kein einziges** Papier ein Ergebnis.
    """
    lade(store, "osnabrueck")
    roh = json.loads((FIXTURES / "osnabrueck_papers.json").read_text(encoding="utf-8"))
    assert all(not c.get("agendaItem") for p in roh for c in p.get("consultation", []))

    batch = get_adapter("allris4").normalize("osnabrueck", store)
    # Ohne passende Sitzung kann auch der Abgleich nichts verbinden …
    assert not [c for c in batch.consultations if c.agenda_item_id]

    # … mit einer Sitzung, deren Punkt genauso heißt, schon.
    titel = batch.papers[0].name
    batch.meetings.append(Meeting("m1", "osnabrueck", None, "Rat", "2026-09-01T16:00"))
    batch.agenda_items.append(AgendaItem("a1", "m1", titel, result_raw="ungeändert beschlossen",
                                         outcome=Outcome.ACCEPTED))
    assert link_by_title(batch) == 1
    verbunden = [c for c in batch.consultations if c.agenda_item_id == "a1"]
    assert verbunden and "#title-match#" in verbunden[0].id, \
        "ein geratener Treffer muss als solcher erkennbar bleiben"


def test_titelabgleich_bleibt_bei_mehrdeutigkeit_stumm():
    """Zwei gleichnamige Punkte: dann lieber kein Ergebnis als ein falsches."""
    batch = Batch(
        papers=[Paper("p1", "x", "Bericht zur Lage")],
        meetings=[Meeting("m1", "x", None, "Rat", "2026-01-01"),
                  Meeting("m2", "x", None, "Rat", "2026-02-01")],
        agenda_items=[
            AgendaItem("a1", "m1", "Bericht zur Lage", result_raw="beschlossen", outcome=Outcome.ACCEPTED),
            AgendaItem("a2", "m2", "Bericht zur Lage", result_raw="beschlossen", outcome=Outcome.ACCEPTED),
        ])
    assert link_by_title(batch) == 0


def test_titelabgleich_ruehrt_verbundene_papiere_nicht_an():
    batch = Batch(
        papers=[Paper("p1", "x", "Mehrweg fördern")],
        meetings=[Meeting("m1", "x", None, "Rat", "2026-01-01")],
        agenda_items=[AgendaItem("a1", "m1", "Mehrweg fördern")],
        consultations=[Consultation("c1", "p1", agenda_item_id="a1")])
    assert link_by_title(batch) == 0
    assert len(batch.consultations) == 1


def test_normalize_title_faellt_ueber_satzzeichen_hinweg_zusammen():
    assert normalize_title("Mehrweg fördern – Müll, Kosten") == \
        normalize_title("Mehrweg fördern  Müll Kosten")
    assert normalize_title(None) == ""


def test_normalize_ist_idempotent(store):
    """Zweimal normalisieren ändert nichts — die Stufe wird oft wiederholt."""
    lade(store, "braunschweig")
    a = get_adapter("allris4").normalize("braunschweig", store)
    b = get_adapter("allris4").normalize("braunschweig", store)
    assert a.counts() == b.counts()
    assert [p.id for p in a.papers] == [p.id for p in b.papers]


def test_normalize_liest_nur_die_letzte_fassung(store):
    """Ein geändertes Papier erzeugt eine zweite Rohzeile — aber ein Objekt."""
    lade(store, "potsdam")
    roh = json.loads((FIXTURES / "potsdam_papers.json").read_text(encoding="utf-8"))
    geaendert = dict(roh[0], name="Titel nach Korrektur")
    store.put_raw_object("potsdam", "paper", geaendert["id"], geaendert)

    batch = get_adapter("allris4").normalize("potsdam", store)
    assert len(batch.papers) == 4
    assert any(p.name == "Titel nach Korrektur" for p in batch.papers)


def test_kein_papier_traegt_eine_person(store):
    """Was der Adapter baut, enthält keine Personen — auch nicht versehentlich."""
    for stadt, dialekt in STAEDTE.items():
        lade(store, stadt)
        batch = get_adapter(dialekt).normalize(stadt, store)
        for p in batch.papers:
            assert not hasattr(p, "originator_person")
        for o in batch.organizations:
            assert "originatorPerson" not in o.name
