"""Der Wahlabend gegen einen ECHTEN, aber kaputten Votemanager.

Die übrigen Wahlabend-Tests ersetzen ``votemanager.fetch`` durch eine
Funktion, die ein fertiges ``Snapshot`` zurückgibt. Das prüft alles ab dem
Zusammensetzen — und genau nichts an dem Stück, das am 13.09.2026 als
einziges nicht in unserer Hand liegt: dem Abruf. Ein 500er auf EINER der drei
Dateien, eine HTML-Wartungsseite mit Status 200, ein Export, der halb
geschrieben ist, ein Server, der 30 Sekunden nicht antwortet — jeder dieser
Fälle ist an einem Wahlabend normal, und keiner davon darf die Seite
anhalten.

Deshalb hier ein eigener HTTP-Server im Thread, der unter den echten Pfaden
ausliefert, was der Test ihm hinlegt, und auf Zuruf kaputtgeht. Geprüft wird
immer über ``GET /api/wahlabend``: Der Endpunkt antwortet in JEDEM Szenario
mit 200 — was klemmt, steht in ``source``.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))
# Wegwerf-Datenbanken und die übrigen Testwerte kommen aus
# `tests/conftest.py` — dort EINMAL je Prozess gesetzt, damit sie nicht an
# der Import-Reihenfolge der Module hängen (siehe die Begründung dort).

from app.election import reference, register, service, votemanager  # noqa: E402
from app.election.votemanager import AreaRow, ListRow  # noqa: E402

FIXTURES = WURZEL / "tests" / "fixtures" / "wahlabend"

STADT = "/daten/opendata/Open-Data-03403000-Stadtratswahl-Stadt.csv"
BEREICHE = "/daten/opendata/Open-Data-03403000-Stadtratswahl-Wahlbereiche.csv"
BEZIRKE = "/daten/opendata/Open-Data-03403000-Stadtratswahl-Wahlbezirk.csv"
TABELLE = "/daten/api/wahl_913/ergebnis_ebene_-6361_id_10358_0.json"
#: Die Ergebnisdarstellung (der Ersatzpfad, ``presentation.py``).
WAHL = "/daten/api/wahl_913/wahl.json"
UEBERSICHT = "/daten/api/wahl_913/uebersicht_ebene_-6362_0.json"


def ergebnis_pfad(nummer: int) -> str:
    return f"/daten/api/wahl_913/ergebnis_ebene_-6362_id_{10400 + nummer}_0.json"

#: Die Kopfzeile des echten Exports von 2026 — Grundlage aller geschriebenen CSVs.
KOPF = (FIXTURES / "2026-wahlbereiche.csv").read_text(encoding="utf-8-sig").splitlines()[0].split(";")

#: So schreibt der Votemanager die Listen in seiner Ergebnistabelle. Wo er vom
#: Kurznamen des Registers abweicht, steht es hier — genau daran muss die
#: Schlüsselwort-Tabelle in ``crosscheck.py`` vorbeikommen.
VOTEMANAGER_NAMEN = {"gruene": "GRÜNE", "piraten": "PIRATEN", "linke": "DIE LINKE."}
ZEILEN_JE_LISTE = ("Summe Partei- und Kandidaten-Stimmen", "Stimmen für die Partei", "Summe Kandidaten-Stimmen")

HTML_SEITE = b"<!DOCTYPE html>\n<html><body><h1>Wartungsarbeiten</h1></body></html>"


# ------------------------------------------------------------------ Der falsche Votemanager

@dataclass
class Stoerung:
    """Was mit einem Pfad nicht stimmt. ``body=None`` heißt: die Datei liefern."""

    status: int = 200
    body: bytes | None = None
    schlaeft: float = 0.0


class Lage:
    """Der Zustand des falschen Votemanagers: Dateien und Störungen."""

    def __init__(self, ordner: Path) -> None:
        self.ordner = ordner
        self.stoerungen: dict[str, Stoerung] = {}
        #: Jeder abgerufene Pfad — um zu prüfen, was der Abruf NICHT holt.
        self.abrufe: list[str] = []

    def leg(self, pfad: str, text: str) -> None:
        ziel = self.ordner / pfad.lstrip("/")
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(text, encoding="utf-8")

    def stoere(self, pfad: str, **kw: object) -> None:
        self.stoerungen[pfad] = Stoerung(**kw)  # type: ignore[arg-type]

    def heile(self) -> None:
        self.stoerungen.clear()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 — von BaseHTTPRequestHandler vorgegeben
        lage: Lage = self.server.lage  # type: ignore[attr-defined]
        pfad = self.path.split("?")[0]
        lage.abrufe.append(pfad)
        stoerung = lage.stoerungen.get(pfad)
        if stoerung and stoerung.schlaeft:
            time.sleep(stoerung.schlaeft)
        datei = lage.ordner / pfad.lstrip("/")
        if stoerung is not None and stoerung.body is not None:
            status, koerper = stoerung.status, stoerung.body
        elif stoerung is not None and stoerung.status != 200:
            status, koerper = stoerung.status, b"Interner Serverfehler"
        elif datei.is_file():
            status, koerper = 200, datei.read_bytes()
        else:
            status, koerper = 404, b"nicht da"
        typ = "application/json" if pfad.endswith(".json") else "text/csv; charset=utf-8"
        try:
            self.send_response(status)
            self.send_header("Content-Type", typ)
            self.send_header("Content-Length", str(len(koerper)))
            self.end_headers()
            self.wfile.write(koerper)
        except OSError:
            pass  # die Gegenseite hat schon aufgegeben — genau der Testfall

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def votemanager_server(tmp_path, monkeypatch):
    """Ein Votemanager auf einem freien Port, der tut, was der Test sagt."""
    lage = Lage(tmp_path / "vm")
    lage.ordner.mkdir(parents=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    server.lage = lage  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("WAHLABEND_VOTEMANAGER_URL", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    monkeypatch.setenv("WAHLABEND_HISTORY_FILE", str(tmp_path / "verlauf.json"))
    monkeypatch.delenv("WAHLABEND_COLUMNS", raising=False)
    register.load.cache_clear()
    votemanager.reset_memory()
    service.reset()
    yield lage
    server.shutdown()
    server.server_close()
    votemanager.reset_memory()
    service.reset()
    register.load.cache_clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


# ------------------------------------------------------------------ Zahlen im Schema 2026

def _z(wert: int | None) -> str:
    return "" if wert is None else str(wert)


def _als_csv(zeilen: list[tuple[int | None, AreaRow]]) -> str:
    """Zeilen im Spaltenschema 2026 — dieselbe Kopfzeile wie der echte Export."""
    out = [";".join(KOPF)]
    for nummer, r in zeilen:
        werte = {
            "datum": "13.09.2026", "wahl": "Stadtratswahl", "ags": "03403000",
            "gebiet-nr": _z(nummer), "gebiet-name": r.name,
            "max-schnellmeldungen": str(r.reports_expected),
            "anz-schnellmeldungen": str(r.reports_received),
            "A": _z(r.eligible), "B": _z(r.voters), "C1": _z(r.invalid_ballots),
            "C2": _z(r.valid_ballots), "D": _z(r.valid_votes),
        }
        for n, lr in r.lists.items():
            werte[f"D{n}_1"] = _z(lr.list_votes)
            werte[f"D{n}_3"] = _z(lr.candidate_sum)
            werte[f"D{n}_4"] = _z(lr.total)
            for k, v in (lr.candidates or {}).items():
                werte[f"D{n}_2_{k}"] = str(v)
        out.append(";".join(werte.get(h, "") for h in KOPF))
    return "\r\n".join(out) + "\r\n"


def _ungezaehlt(row: AreaRow) -> AreaRow:
    lists = {i: ListRow(i, None, None, None, None) for i in row.lists}
    return AreaRow(row.name, row.number, row.reports_expected, 0, None, None, None, None, None, lists)


def _summe(name: str, nummer: int | None, rows: list[AreaRow]) -> AreaRow:
    def add(werte: list[int | None]) -> int | None:
        bekannt = [w for w in werte if w is not None]
        return sum(bekannt) if bekannt else None

    lists: dict[int, ListRow] = {}
    for i in sorted({i for r in rows for i in r.lists}):
        lrs = [r.lists[i] for r in rows if i in r.lists]
        cands: dict[int, int] = {}
        gab_welche = False
        for lr in lrs:
            if lr.candidates is not None:
                gab_welche = True
                for k, v in lr.candidates.items():
                    cands[k] = cands.get(k, 0) + v
        lists[i] = ListRow(i, add([lr.total for lr in lrs]), add([lr.list_votes for lr in lrs]),
                           add([lr.candidate_sum for lr in lrs]), cands if gab_welche else None)
    return AreaRow(
        name=name, number=nummer,
        reports_expected=sum(r.reports_expected for r in rows),
        reports_received=sum(r.reports_received for r in rows),
        eligible=add([r.eligible for r in rows]), voters=add([r.voters for r in rows]),
        invalid_ballots=add([r.invalid_ballots for r in rows]), valid_ballots=add([r.valid_ballots for r in rows]),
        valid_votes=add([r.valid_votes for r in rows]), lists=lists,
    )


def _stand(ausgezaehlt: int) -> tuple[list[AreaRow], AreaRow, list[int | None], list[AreaRow]]:
    """Die 2021er Ergebnisse, umgeschlüsselt auf die Spaltenindizes von 2026,
    davon die ersten ``ausgezählt`` Bezirke: (Wahlbereiche, Stadt, Bezirksnummern, Bezirke)."""
    reg, ref = register.load(), reference.load()
    bezirke = [ref.remap(r, reg) for r in ref.districts]
    bezirke = [b if i < ausgezaehlt else _ungezaehlt(b) for i, b in enumerate(bezirke)]
    nummern = [votemanager.district_number(b.name, None) for b in bezirke]

    bereiche: list[AreaRow] = []
    for a in reg.areas:
        meine = [b for b, n in zip(bezirke, nummern)
                 if n is not None and votemanager.area_of_district(n) == a.number]
        bereiche.append(_summe(f"Wahlbereich {a.number}", a.number, meine))
    return bereiche, _summe("Stadt Oldenburg", None, bereiche), nummern, bezirke


def leg_ergebnisse(lage: Lage, ausgezaehlt: int) -> None:
    """Die drei CSVs mit echten Zahlen."""
    bereiche, stadt, nummern, bezirke = _stand(ausgezaehlt)
    lage.leg(STADT, _als_csv([(None, stadt)]))
    lage.leg(BEREICHE, _als_csv([(b.number, b) for b in bereiche]))
    lage.leg(BEZIRKE, _als_csv(list(zip(nummern, bezirke))))


def _ohne_personen(row: AreaRow) -> AreaRow:
    """Gesamt- und Listenstimmen ja, Kandidatenspalten leer — so sähe eine
    CSV aus, in der die Personenstimmen nachhinken."""
    lists = {i: ListRow(i, lr.total, lr.list_votes, None, None) for i, lr in row.lists.items()}
    return AreaRow(row.name, row.number, row.reports_expected, row.reports_received, row.eligible, row.voters,
                   row.invalid_ballots, row.valid_ballots, row.valid_votes, lists)


# ------------------------------------------------------------------ Die Ergebnisdarstellung

def _zahl(wert: int | None) -> str:
    """So schreibt der Votemanager Zahlen: mit Tausenderpunkt, leer für „noch nicht"."""
    return "" if wert is None else f"{wert:,}".replace(",", ".")


def _plaetze_2026(index: int) -> int:
    """Wie viele Kandidatenspalten die Kopfzeile von 2026 für Liste ``index`` hat."""
    return sum(1 for h in KOPF if h.startswith(f"D{index}_2_"))


def _als_ergebnis_json(row: AreaRow, titel: str, sitze: dict[str, int] | None = None,
                       namen: dict[str, str] | None = None) -> str:
    """Ein Gebiets-JSON in der Form der Ergebnisdarstellung (s. ``presentation.py``)."""
    reg = register.load()
    zeilen: list[dict] = []
    for i, lr in sorted(row.lists.items()):
        p = reg.party(i)
        assert p is not None
        if lr.total is None:
            continue
        if p.kind == "einzelbewerber":
            zeilen.append({"label": {"labelKurz": f"{p.short}, Einzelwahlvorschlag Stille"}, "zahl": _zahl(lr.total)})
            continue
        name = (namen or {}).get(p.slug) or VOTEMANAGER_NAMEN.get(p.slug, p.short)
        sub = None
        if lr.candidates is not None:
            # Die Darstellung führt JEDE Bewerber*in als Zeile, auch ohne
            # Stimme — eine Lücke in der Reihenfolge gibt es dort nicht. Und
            # nicht mehr Plätze, als die Liste 2026 hat: Die 2021er Zahlen
            # tragen hier und da einen zwölften Platz, den die CSV-Kopfzeile
            # von 2026 ebenfalls nicht kennt.
            plaetze = _plaetze_2026(i)
            sub = [{"label": {"labelKurz": f"Platz {k}"}, "zahl": _zahl(lr.candidates.get(k, 0)), "prozent": ""}
                   for k in range(1, min(max(lr.candidates, default=0), plaetze) + 1)]
        zeilen += [
            {"label": {"labelKurz": f"{name} - {ZEILEN_JE_LISTE[0]}"}, "zahl": _zahl(lr.total)},
            {"label": {"labelKurz": f"{name} - {ZEILEN_JE_LISTE[1]}"}, "zahl": _zahl(lr.list_votes)},
            {"label": {"labelKurz": f"{name} - {ZEILEN_JE_LISTE[2]}"}, "zahl": _zahl(lr.candidate_sum),
             **({"sub_zeilen": sub} if sub is not None else {})},
        ]
    info = {
        "titel": titel,
        "hinweis": [f"{row.reports_received} von {row.reports_expected} Ergebnissen"],
        "tabelle": {"zeilen": [
            {"label": {"labelKurz": "Wahlberechtigte"}, "zahl": _zahl(row.eligible)},
            {"label": {"labelKurz": "Wählerinnen/Wähler"}, "zahl": _zahl(row.voters)},
            {"label": {"labelKurz": "ungültige Stimmzettel"}, "zahl": _zahl(row.invalid_ballots)},
            {"label": {"labelKurz": "gültige Stimmzettel"}, "zahl": _zahl(row.valid_ballots)},
            {"label": {"labelKurz": "gültige Stimmen"}, "zahl": _zahl(row.valid_votes)},
        ]},
    }
    komponente: dict = {"tabelle": {"zeilen": zeilen}, "info": info}
    if sitze is not None:
        entries = [{"label": VOTEMANAGER_NAMEN.get(slug, reg.by_slug(slug).short), "sitze": n}  # type: ignore[union-attr]
                   for slug, n in sitze.items()]
        komponente["sitze"] = {"hinweis": f"Es wurden {sum(sitze.values())} Sitze vergeben.",
                               "tortenDiagramm": {"entries": entries}}
    return json.dumps({"zeitstempel": "13.09.2026 20:15", "Komponente": komponente}, ensure_ascii=False)


def leg_praesentation(lage: Lage, bereiche: list[AreaRow], stadt: AreaRow | None, *,
                      sitze: dict[str, int] | None = None, namen: dict[str, str] | None = None) -> None:
    """Die Ergebnisdarstellung: ``wahl.json``, die Übersicht der Wahlbereiche,
    je Wahlbereich ein Ergebnis — und die Stadt, wenn gewünscht."""
    reg = register.load()
    lage.leg(WAHL, json.dumps({"titel": "Stadtratswahl", "menu_links": [
        {"id": "ebene_-6361_id_10358", "type": "ergebnis", "title": "Stadt Oldenburg"},
        {"id": "ebene_-6362", "type": "uebersicht", "title": "Wahlbereiche"},
        {"id": "ebene_6", "type": "uebersicht", "title": "Wahlbezirke"}]}))
    zeilen = []
    for b in bereiche:
        a = next(a for a in reg.areas if a.number == b.number)
        label = f"{a.roman} - {a.name}"
        zeilen.append({"label": label, "link": {"id": f"ebene_-6362_id_{10400 + a.number}", "type": "ergebnis", "title": label},
                       "statusString": f"{b.reports_received} von {b.reports_expected}"})
        lage.leg(ergebnis_pfad(a.number), _als_ergebnis_json(b, f"Stadt Oldenburg - {label}", namen=namen))
    zeilen.append({"label": "Stadt Oldenburg", "link": {"id": "ebene_-6361_id_10358", "type": "ergebnis", "title": "Stadt Oldenburg"}})
    lage.leg(UEBERSICHT, json.dumps({"zeitstempel": "13.09.2026 20:15", "tabelle": {"header": [], "zeilen": zeilen}},
                                    ensure_ascii=False))
    if stadt is not None:
        lage.leg(TABELLE, _als_ergebnis_json(stadt, "Stadt Oldenburg - Gesamtergebnis", sitze=sitze, namen=namen))


def leg_leere_praesentation(lage: Lage) -> None:
    """So liegen die JSONs am Nachmittag da: nur ein Zeitstempel."""
    leer = json.dumps({"zeitstempel": "13.09.2026 12:54", "file_version": "26.08.03"})
    lage.leg(UEBERSICHT, leer)
    lage.leg(TABELLE, leer)


def leg_leere_dateien(lage: Lage) -> None:
    """Die echten Exporte vom Nachmittag: Kopfzeile, Gebiete, sonst nichts."""
    for pfad, name in ((STADT, "2026-stadt.csv"), (BEREICHE, "2026-wahlbereiche.csv"),
                       (BEZIRKE, "2026-wahlbezirk.csv")):
        lage.leg(pfad, (FIXTURES / name).read_text(encoding="utf-8-sig"))


def leg_tabelle(lage: Lage, reihenfolge: list[str]) -> None:
    """Die Ergebnistabelle der Stadt-Ebene in der gegebenen Spaltenreihenfolge."""
    reg = register.load()
    zeilen: list[dict] = [{"label": {"labelKurz": "Wahlberechtigte"}},
                          {"label": {"labelKurz": "Gültige Stimmen"}}]
    for slug in reihenfolge:
        p = reg.by_slug(slug)
        assert p is not None
        if p.kind == "einzelbewerber":
            zeilen.append({"label": {"labelKurz": f"{p.short}, Einzelwahlvorschlag Stille"}})
            continue
        name = VOTEMANAGER_NAMEN.get(slug, p.short)
        zeilen += [{"label": {"labelKurz": f"{name} - {suffix}"}} for suffix in ZEILEN_JE_LISTE]
    lage.leg(TABELLE, json.dumps({"Komponente": {"tabelle": {"zeilen": zeilen}}}, ensure_ascii=False))


def standardreihenfolge() -> list[str]:
    return [p.slug for p in register.load().parties]


def getauscht(slug_a: str, slug_b: str) -> list[str]:
    reihe = standardreihenfolge()
    i, j = reihe.index(slug_a), reihe.index(slug_b)
    reihe[i], reihe[j] = reihe[j], reihe[i]
    return reihe


def hol(client) -> dict:
    """Ein Abruf über den Endpunkt. 200 ist nicht verhandelbar."""
    r = client.get("/api/wahlabend")
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ (a) vor der Auszählung

def test_leere_dateien_ergeben_phase_before(votemanager_server, client):
    leg_leere_dateien(votemanager_server)
    d = hol(client)
    assert d["phase"] == "before"
    assert d["source"]["ok"] is True and d["source"]["error"] is None
    assert d["progress"] == {"districts_total": 133, "districts_counted": 0}
    # Vor der Auszählung gibt es die Ergebnistabelle noch gar nicht — die
    # Spaltenprobe darf daran nicht scheitern und nichts melden.
    assert votemanager.fetch().warnings == []


# ------------------------------------------------------------------ (b)/(c) Zahlen und Spalten

def test_ausgezaehlte_zeilen_ergeben_sitze_ohne_warnung(votemanager_server, client):
    leg_ergebnisse(votemanager_server, 40)
    leg_tabelle(votemanager_server, standardreihenfolge())
    d = hol(client)
    assert d["phase"] == "counting"
    assert d["source"]["ok"] is True and d["source"]["error"] is None
    assert d["progress"] == {"districts_total": 133, "districts_counted": 40}
    assert sum(p["seats"] or 0 for p in d["parties"]) > 0 and d["mandates"]
    assert d["person_votes_available"] is True
    assert votemanager.fetch().warnings == []


def test_vertauschte_spalten_beim_votemanager_werden_gemeldet(votemanager_server, client):
    leg_ergebnisse(votemanager_server, 40)
    leg_tabelle(votemanager_server, getauscht("volt", "piraten"))
    d = hol(client)
    assert d["phase"] == "counting" and d["source"]["ok"] is True

    warnungen = votemanager.fetch().warnings
    assert warnungen, "vertauschte Spalten blieben unbemerkt"
    assert any("D7" in w and "PIRATEN" in w and "Volt" in w for w in warnungen), warnungen
    # Ein Hinweis ist kein Ausfall: Die Zahlen bleiben, wie sie gemeldet wurden.
    assert d["source"]["error"] is None


def test_kopfzeile_ohne_netz_meldet_falsche_listenlaengen(votemanager_server, client):
    """Die zweite Probe braucht keine Ergebnisse: Passen die Kandidatenspalten
    nicht zu den Listenlängen des Registers, steht die Zuordnung schief."""
    roh = (FIXTURES / "2026-wahlbereiche.csv").read_text(encoding="utf-8-sig").splitlines()
    # D1 (GRÜNE, 10 Bewerber*innen) verliert eine Kandidatenspalte, und der
    # Einzelwahlvorschlag D11 bekommt eine, die es dort nicht geben darf.
    roh[0] = roh[0].replace("D1_2_10;", "D1_2_9;") + ";D11_2_1"
    votemanager_server.leg(BEREICHE, "\r\n".join(roh) + "\r\n")
    votemanager_server.leg(STADT, (FIXTURES / "2026-stadt.csv").read_text(encoding="utf-8-sig"))
    votemanager_server.leg(BEZIRKE, (FIXTURES / "2026-wahlbezirk.csv").read_text(encoding="utf-8-sig"))

    d = hol(client)
    assert d["phase"] == "before" and d["source"]["ok"] is True
    warnungen = votemanager.fetch().warnings
    assert any("D1" in w and "10" in w for w in warnungen), warnungen
    assert any("D11" in w and "Einzelwahlvorschlag" in w for w in warnungen), warnungen


# ------------------------------------------------------------------ (d)–(h) eine Datei geht kaputt

@pytest.mark.parametrize("stoerung, was", [
    ({"status": 500}, "Serverfehler"),
    ({"body": HTML_SEITE}, "HTML-Seite mit Status 200"),
    ({"body": b""}, "leere Datei"),
])
def test_kaputte_wahlbereichsdatei_haelt_ihren_letzten_guten_stand(votemanager_server, client, stoerung, was):
    leg_ergebnisse(votemanager_server, 40)
    leg_tabelle(votemanager_server, standardreihenfolge())
    gut = hol(client)
    assert gut["source"]["ok"] is True and gut["progress"]["districts_counted"] == 40

    votemanager_server.stoere(BEREICHE, **stoerung)
    service.reset()
    d = hol(client)
    assert d["source"]["ok"] is False, was
    assert "Wahlbereiche" in (d["source"]["error"] or ""), (was, d["source"]["error"])
    # Die anderen beiden Dateien wurden frisch übernommen, die Wahlbereiche
    # stehen auf ihrem letzten guten Stand — die Seite zeigt weiter Sitze.
    assert d["phase"] == "counting"
    assert d["progress"] == {"districts_total": 133, "districts_counted": 40}
    assert [a["number"] for a in d["areas"]] == [1, 2, 3, 4, 5, 6]
    assert sum(p["seats"] or 0 for p in d["parties"]) > 0
    assert "alter Stand" in d["source"]["error"]


def test_ohne_jeden_guten_stand_bleibt_die_seite_stehen(votemanager_server, client):
    """Der Kaltstart: Nichts liegt im Gedächtnis, alle drei Dateien fehlen.
    Auch das ist eine Antwort mit 200 — nur eben eine leere mit Fehlertext."""
    d = hol(client)
    assert d["source"]["ok"] is False
    fehler = d["source"]["error"] or ""
    assert all(name in fehler for name in ("Stadt", "Wahlbereiche", "Wahlbezirke")), fehler
    assert "keine Daten" in fehler
    assert d["phase"] == "before" and [a["number"] for a in d["areas"]] == [1, 2, 3, 4, 5, 6]


def test_zeitueberschreitung_haelt_die_antwort_nicht_auf(votemanager_server, client, monkeypatch):
    leg_ergebnisse(votemanager_server, 40)
    leg_tabelle(votemanager_server, standardreihenfolge())
    assert hol(client)["source"]["ok"] is True

    monkeypatch.setattr(votemanager, "TIMEOUT", (1, 1))
    votemanager_server.stoere(BEREICHE, schlaeft=4.0)
    service.reset()
    start = time.monotonic()
    d = hol(client)
    dauer = time.monotonic() - start

    assert dauer < 5, f"der Abruf hing {dauer:.1f} s"
    assert d["source"]["ok"] is False and "Wahlbereiche" in (d["source"]["error"] or "")
    assert d["progress"] == {"districts_total": 133, "districts_counted": 40}


def test_nach_der_stoerung_zaehlt_wieder_frisch(votemanager_server, client, monkeypatch):
    leg_ergebnisse(votemanager_server, 40)
    leg_tabelle(votemanager_server, standardreihenfolge())
    assert hol(client)["progress"]["districts_counted"] == 40

    votemanager_server.stoere(BEREICHE, status=500)
    service.reset()
    assert hol(client)["source"]["ok"] is False

    votemanager_server.heile()
    leg_ergebnisse(votemanager_server, 60)
    service.reset()
    d = hol(client)
    assert d["source"]["ok"] is True and d["source"]["error"] is None
    assert d["progress"] == {"districts_total": 133, "districts_counted": 60}
    assert votemanager.fetch().warnings == []


# ------------------------------------------------------------------ (j) der Ersatzpfad: die Ergebnisdarstellung

def test_ohne_csv_kommen_die_zahlen_aus_der_ergebnisdarstellung(votemanager_server, client):
    """Die CSVs fehlen ganz (404) — die Website zeigt längst Zahlen. Dann
    kommen Sitze UND Namen aus ihren JSON-Dateien; der CSV-Ausfall bleibt
    trotzdem als Fehler stehen, denn er ist einer."""
    bereiche, stadt, _, _ = _stand(40)
    leg_praesentation(votemanager_server, bereiche, stadt)
    d = hol(client)
    assert d["phase"] == "counting"
    assert d["progress"] == {"districts_total": 133, "districts_counted": 40}
    assert sum(p["seats"] or 0 for p in d["parties"]) > 0 and d["mandates"]
    assert d["person_votes_available"] is True
    assert all(m["name"] for m in d["mandates"]), "Namen fehlen, obwohl die Personenstimmen da sind"
    assert d["source"]["ok"] is False and "Wahlbereiche" in (d["source"]["error"] or "")
    hinweise = [n for n in d["notes"] if "Ergebnisdarstellung" in n]
    assert len(hinweise) == 1 and "I - Stadtmitte Nord" in hinweise[0] and "Stadt" in hinweise[0], d["notes"]
    # Der Ersatz liefert dieselben Zahlen wie der Hauptweg.
    votemanager.reset_memory()
    service.reset()
    leg_ergebnisse(votemanager_server, 40)
    leg_tabelle(votemanager_server, standardreihenfolge())
    csv = hol(client)
    assert [(p["slug"], p["votes"], p["seats"]) for p in csv["parties"]] == [(p["slug"], p["votes"], p["seats"]) for p in d["parties"]]
    assert {(m["slug"], m["area"], m["position"], m["kind"]) for m in csv["mandates"]} == {(m["slug"], m["area"], m["position"], m["kind"]) for m in d["mandates"]}


def test_csv_ohne_personenstimmen_holt_sie_aus_der_ergebnisdarstellung(votemanager_server, client):
    """Der wahrscheinlichere Fall: Die CSV kommt, aber die Kandidatenspalten
    bleiben leer — Sitze ja, Namen nein. Die Darstellung trägt die Namen."""
    bereiche, stadt, nummern, bezirke = _stand(40)
    votemanager_server.leg(STADT, _als_csv([(None, _ohne_personen(stadt))]))
    votemanager_server.leg(BEREICHE, _als_csv([(b.number, _ohne_personen(b)) for b in bereiche]))
    votemanager_server.leg(BEZIRKE, _als_csv([(n, _ohne_personen(b)) for n, b in zip(nummern, bezirke)]))
    leg_praesentation(votemanager_server, bereiche, stadt)
    d = hol(client)
    assert d["source"]["ok"] is True and d["source"]["error"] is None
    assert d["phase"] == "counting" and d["person_votes_available"] is True
    assert all(m["name"] for m in d["mandates"])
    assert any("Ergebnisdarstellung" in n for n in d["notes"]), d["notes"]
    # Die Bezirke bleiben die der CSV — die Hochrechnung hängt an ihnen.
    assert d["progress"] == {"districts_total": 133, "districts_counted": 40}


def test_mit_vollstaendiger_csv_bleibt_die_darstellung_ungefragt(votemanager_server, client):
    """Trägt die CSV in jedem Wahlbereich Personenstimmen, gibt es nichts zu
    ersetzen — und dann werden die JSONs auch nicht geholt. Acht Abrufe je
    Minute sind sonst Lärm beim Votemanager, ohne Gewinn. (Solange EIN
    Wahlbereich noch ohne Personenstimmen dasteht, wird nachgesehen — das
    ist der Fall, für den der Ersatz gebaut ist.)"""
    leg_ergebnisse(votemanager_server, 133)
    leg_tabelle(votemanager_server, standardreihenfolge())
    bereiche, stadt, _, _ = _stand(133)
    leg_praesentation(votemanager_server, bereiche, stadt)
    votemanager_server.abrufe.clear()
    d = hol(client)
    assert d["person_votes_available"] is True
    assert UEBERSICHT not in votemanager_server.abrufe
    assert not any(p.startswith("/daten/api/wahl_913/ergebnis_ebene_-6362") for p in votemanager_server.abrufe)
    assert not any("Ergebnisdarstellung" in n for n in d["notes"])


def test_json_ohne_personen_ersetzt_leere_csv(votemanager_server, client):
    """PR 0 (Tippspiel-Plan): Die CSV liegt bei 0 von N Meldungen, die
    Ergebnisdarstellung zeigt schon Zahlen — aber ohne Personenstimmen.
    Vorher hätte ``_better`` das verworfen, weil auch die JSON-Zeile keine
    Personen trägt; jetzt entscheidet zuerst der Auszählungsstand."""
    leg_ergebnisse(votemanager_server, 0)
    leg_tabelle(votemanager_server, standardreihenfolge())
    bereiche, stadt, _, _ = _stand(133)
    leg_praesentation(votemanager_server, [_ohne_personen(b) for b in bereiche], _ohne_personen(stadt))
    d = hol(client)
    assert d["person_votes_available"] is False
    assert sum(p["votes"] or 0 for p in d["parties"]) > 0, "die JSON-Zahlen wurden nicht übernommen"
    assert any("weiter als die Open-Data-CSV" in n for n in d["notes"]), d["notes"]


def test_json_weiter_als_csv_gewinnt(votemanager_server, client):
    """Ein Wahlbereich ist in der CSV nur teilweise ausgezählt (mit
    Personenstimmen); die Ergebnisdarstellung zeigt für denselben Bereich
    schon den vollen Stand. Vorher gewann die CSV automatisch, weil sie
    bereits Personenstimmen trug — jetzt gewinnt, wer weiter ist."""
    leg_ergebnisse(votemanager_server, 40)
    leg_tabelle(votemanager_server, standardreihenfolge())
    snap = votemanager.fetch()
    unvollstaendige = [a for a in snap.areas if a.reports_received < a.reports_expected]
    assert unvollstaendige, "Testannahme verletzt: bei 40 von 133 Bezirken ist kein Wahlbereich unvollständig"
    teil = unvollstaendige[0]

    bereiche, stadt, _, _ = _stand(133)
    leg_praesentation(votemanager_server, bereiche, stadt)
    votemanager.reset_cache()
    hol(client)
    snap2 = votemanager.fetch()
    voll = next(a for a in snap2.areas if a.number == teil.number)
    assert voll.reports_received == voll.reports_expected, "die vollständigere JSON-Zeile hätte gewinnen müssen"
    assert any("weiter als die Open-Data-CSV" in n for n in snap2.warnings), snap2.warnings


def test_csv_weiter_als_json_bleibt(votemanager_server, client):
    """Umgekehrter Fall: Die CSV ist weiter als die Ergebnisdarstellung.
    Dann bleibt die CSV-Zeile stehen — kein Rückschritt durch das JSON."""
    leg_ergebnisse(votemanager_server, 90)
    leg_tabelle(votemanager_server, standardreihenfolge())
    snap = votemanager.fetch()
    unvollstaendige = [a for a in snap.areas if a.reports_received < a.reports_expected]
    assert unvollstaendige, "Testannahme verletzt: bei 90 von 133 Bezirken ist kein Wahlbereich unvollständig"
    teil = unvollstaendige[0]

    bereiche, stadt, _, _ = _stand(40)  # die Ergebnisdarstellung hinkt hinterher
    leg_praesentation(votemanager_server, bereiche, stadt)
    votemanager.reset_cache()
    hol(client)
    snap2 = votemanager.fetch()
    unveraendert = next(a for a in snap2.areas if a.number == teil.number)
    assert unveraendert.reports_received == teil.reports_received, "die ältere JSON-Zeile hätte NICHT gewinnen dürfen"
    assert not any("weiter als die Open-Data-CSV" in n for n in snap2.warnings), snap2.warnings


def test_stadtzeile_folgt_derselben_regel(votemanager_server, client):
    """Die Stadtzeile folgt seit PR 0 derselben ``_better``-Regel wie die
    Wahlbereiche — vorher wurde sie nur ersetzt, wenn die CSV-Stadt GAR NICHT
    ausgezählt war, ein Teilstand blockierte die JSON-Fassung für immer."""
    leg_ergebnisse(votemanager_server, 40)
    leg_tabelle(votemanager_server, standardreihenfolge())
    snap = votemanager.fetch()
    assert snap.city and snap.city[0].counted, "Testannahme verletzt: die Stadtzeile hat schon einen Teilstand"

    bereiche, stadt, _, _ = _stand(133)
    leg_praesentation(votemanager_server, bereiche, stadt)
    votemanager.reset_cache()
    hol(client)
    snap2 = votemanager.fetch()
    assert snap2.city[0].reports_received == stadt.reports_received
    assert any("Stadt" in n and "weiter als die Open-Data-CSV" in n for n in snap2.warnings), snap2.warnings


def test_needs_presentation_bei_unvollstaendiger_zaehlung_trotz_personen():
    """Unit-Test des Kerns von PR 0: Eine Zeile mit Personenstimmen, aber
    unvollständigem Meldungsstand, löst trotzdem einen Blick in die
    Ergebnisdarstellung aus — die alte Prüfung fragte nur nach Personen."""
    voll = AreaRow("Wahlbereich I", 1, 22, 22, 1000, 800, 10, 790, 780,
                   {1: ListRow(1, 400, 300, 100, {1: 50, 2: 50})})
    teil = AreaRow("Wahlbereich I", 1, 22, 10, 1000, 400, 5, 395, 390,
                   {1: ListRow(1, 200, 150, 50, {1: 25, 2: 25})})
    assert votemanager._needs_presentation([voll]) is False
    assert votemanager._needs_presentation([teil]) is True


@pytest.mark.parametrize("csv_reports, json_reports, csv_hat_personen, json_hat_personen, erwartet", [
    (0, 0, False, False, False),   # Gleichstand, keine Seite hat Personen — kein Wechsel
    (10, 20, False, False, True),  # JSON weiter, trotz fehlender Personen beiderseits
    (20, 10, True, False, False),  # CSV weiter UND hat schon Personen — JSON (weniger weit) gewinnt nicht
    (15, 15, False, True, True),   # Gleichstand, nur JSON hat Personen — alte Regel bleibt
    (15, 15, True, True, False),   # Gleichstand, beide haben Personen — kein Wechsel
])
def test_better_vergleicht_zuerst_den_auszaehlungsstand(csv_reports, json_reports, csv_hat_personen, json_hat_personen, erwartet):
    """Unit-Test der Kernfunktion: Meldungsstand zuerst, Personenstimmen nur
    als Tie-Breaker bei Gleichstand — nicht mehr das alleinige Kriterium."""
    def zeile(reports: int, personen: bool) -> AreaRow:
        cands = {1: 10} if personen else None
        return AreaRow("Wahlbereich I", 1, 22, reports, 1000, 800, 10, 790, 780,
                       {1: ListRow(1, 400, 300, 100, cands)})

    csv_row = zeile(csv_reports, csv_hat_personen)
    json_row = zeile(json_reports, json_hat_personen)
    assert votemanager._better(csv_row, json_row) is erwartet


def test_better_ohne_csv_zeile_gewinnt_json_immer():
    """Unverändert gegenüber vorher: Fehlt die CSV-Zeile ganz, gilt die
    JSON-Zeile immer als besser — auch ohne jede Meldung."""
    json_row = AreaRow("Wahlbereich I", 1, 22, 0, None, None, None, None, None, {})
    assert votemanager._better(None, json_row) is True


def test_vor_der_auszaehlung_ist_die_darstellung_leer_und_stoert_nicht(votemanager_server, client):
    leg_leere_dateien(votemanager_server)
    leg_leere_praesentation(votemanager_server)
    d = hol(client)
    assert d["phase"] == "before" and d["source"]["ok"] is True
    assert not any("Ergebnisdarstellung" in n for n in d["notes"])


def test_unbekannte_liste_in_der_darstellung_wird_gemeldet_und_nicht_geraten(votemanager_server, client):
    bereiche, stadt, _, _ = _stand(40)
    leg_praesentation(votemanager_server, bereiche, stadt, namen={"volt": "Wählerliste Zukunft"})
    d = hol(client)
    # Kein Wahlbereich ist brauchbar — die Liste steht in jedem. Also nichts
    # statt falscher Zahlen, und ein Hinweis, der die Liste beim Namen nennt.
    assert d["phase"] == "before"
    assert any("Wählerliste Zukunft" in n and "außen vor" in n for n in d["notes"]), d["notes"]


def test_sitzverteilung_des_votemanagers_als_gegenprobe(votemanager_server, client):
    """Am Ende der Auszählung weist der Votemanager selbst Sitze aus. Stimmen
    sie mit der eigenen Zuteilung überein, schweigt die Seite; weichen sie ab,
    steht es in ``notes``."""
    leg_ergebnisse(votemanager_server, 133)
    bereiche, stadt, _, _ = _stand(133)
    eigene = {p["slug"]: p["seats"] for p in hol(client)["parties"] if p["seats"]}
    assert eigene and hol(client)["phase"] == "complete"

    leg_praesentation(votemanager_server, bereiche, stadt, sitze=eigene)
    votemanager.reset_cache()
    service.reset()
    assert not any("weicht" in n for n in hol(client)["notes"])

    falsch = dict(eigene)
    erster = next(iter(falsch))
    falsch[erster] -= 1
    leg_praesentation(votemanager_server, bereiche, stadt, sitze=falsch)
    votemanager.reset_cache()
    service.reset()
    d = hol(client)
    hinweise = [n for n in d["notes"] if "weicht" in n]
    assert len(hinweise) == 1 and f"{falsch[erster]} statt {eigene[erster]}" in hinweise[0], d["notes"]


# ------------------------------------------------------------------ (i) der Notausgang

def test_wahlabend_columns_dreht_die_spaltenzuordnung(votemanager_server, client, monkeypatch):
    leg_leere_dateien(votemanager_server)
    vorgabe = standardreihenfolge()
    assert vorgabe[6:8] == ["volt", "piraten"]

    monkeypatch.setenv("WAHLABEND_COLUMNS", ",".join(getauscht("volt", "piraten")))
    register.load.cache_clear()
    service.reset()
    d = hol(client)
    assert [p["slug"] for p in d["parties"]][6:8] == ["piraten", "volt"]
    assert [p["index"] for p in d["parties"]] == list(range(1, len(vorgabe) + 1))
    # Die Kandidatenlisten hängen am Slug, nicht am Index.
    volt = next(p for p in d["parties"] if p["slug"] == "volt")
    assert volt["index"] == 8 and volt["candidates_total"] == 13

    monkeypatch.delenv("WAHLABEND_COLUMNS")
    register.load.cache_clear()
    service.reset()
    assert [p["slug"] for p in hol(client)["parties"]][6:8] == ["volt", "piraten"]


@pytest.mark.parametrize("fall", ["unbekannt", "zu-kurz", "doppelt"])
def test_unbrauchbares_wahlabend_columns_laesst_die_vorgabe_stehen(votemanager_server, monkeypatch, fall):
    """Halb angewandt wäre schlimmer als gar nicht: Ein Tippfehler in der
    ``.env`` darf die Zuordnung nicht verschieben, sondern muss sie lassen."""
    vorgabe = standardreihenfolge()
    werte = {
        "unbekannt": ",".join(["gibtsnicht"] + vorgabe[1:]),
        "zu-kurz": ",".join(vorgabe[:-1]),
        # Richtige Anzahl, aber „spd" zweimal — „dava" fehlt dafür.
        "doppelt": ",".join(["spd" if s == "dava" else s for s in vorgabe]),
    }
    monkeypatch.setenv("WAHLABEND_COLUMNS", werte[fall])
    register.load.cache_clear()
    assert [p.slug for p in register.load().parties] == vorgabe
    assert [p.index for p in register.load().parties] == list(range(1, len(vorgabe) + 1))
