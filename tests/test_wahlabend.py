"""Wahlabend zur Ratswahl 2026: Sitzzuteilung, Register, Votemanager-CSVs, Endpunkt.

Die harte Zusage ist die Sitzzuteilung: Sie muss das amtliche Ergebnis von
2021 exakt reproduzieren, alle 50 Mandate samt „direkt"/„Listenplatz n". Das
Verfahren (NKWG §§ 36, 37) steht in ``web/backend/app/election/seats.py``.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))
_TMP = tempfile.mkdtemp()
os.environ.setdefault("RATSLOTSE_DB", str(Path(_TMP) / "ratslotse.sqlite"))
os.environ.setdefault("COUNCIL_DB", str(Path(_TMP) / "council.sqlite"))
os.environ.setdefault("WEB_JWT_SECRET", "test-secret")
os.environ.setdefault("DISABLE_RATE_LIMIT", "1")
# Der Verlauf des Wahlabends gehört im Test in den tmp-Ordner, nie nach data/.
os.environ.setdefault("WAHLABEND_HISTORY_FILE", str(Path(_TMP) / "wahlabend-verlauf.json"))

from app.election import reference, register, service, votemanager  # noqa: E402
from app.election.projection import project  # noqa: E402
from app.election.seats import DistrictList, allocate, hare_niemeyer, party_seat_margins, votes_to_seat  # noqa: E402

REFERENZ = WURZEL / "kommunalwahl" / "referenz-2021"
FIXTURES = WURZEL / "tests" / "fixtures" / "wahlabend"
KANDIDATEN = WURZEL / "kommunalwahl" / "kandidaten.json"


# ------------------------------------------------------------------ Hare/Niemeyer

def test_hare_niemeyer_rechenbeispiel_braunschweig():
    """Das Beispiel „Musterstadt" aus dem Erklärblatt des Wahlamts Braunschweig
    (2006): 20 Sitze, drei Parteien, zwei Wahlbereiche."""
    sitze, lose = hare_niemeyer({"D1": 7300, "D2": 6700, "D3": 2400}, 20)
    assert sitze == {"D1": 9, "D2": 8, "D3": 3} and lose == []
    assert hare_niemeyer({1: 4200, 2: 3100}, 9)[0] == {1: 5, 2: 4}
    assert hare_niemeyer({"list": 1400, "persons": 2800}, 5)[0] == {"list": 2, "persons": 3}


def test_hare_niemeyer_meldet_losfall_und_mehrheitsklausel():
    _, lose = hare_niemeyer({"a": 100, "b": 100, "c": 50}, 3)
    assert lose == []
    _, lose = hare_niemeyer({"a": 10, "b": 10, "c": 10}, 2)
    assert lose, "gleiche Reste ohne Losvermerk"
    # § 36 Abs. 3: über die Hälfte der Stimmen, aber nach Bruchteilen nur die
    # Hälfte der Sitze — der Restsitz geht vorab an die Mehrheit.
    lists = [DistrictList("A", 1, 501, 501, {1: 0}, 5), DistrictList("B", 1, 499, 499, {1: 0}, 5)]
    assert allocate(lists, 4).seats_by_party == {"A": 3, "B": 1}
    lists = [DistrictList("A", 1, 5001, 5001, {1: 0}, 9), DistrictList("B", 1, 2500, 2500, {1: 0}, 9), DistrictList("C", 1, 2499, 2499, {1: 0}, 9)]
    assert allocate(lists, 8).seats_by_party["A"] == 5


# ------------------------------------------------------------------ 2021 amtlich

def _listen_2021() -> tuple[list[DistrictList], dict]:
    meta = json.loads((REFERENZ / "ratswahl-2021.json").read_text(encoding="utf-8"))
    label = {int(p["index"]): p["label"] for p in meta["parteien"]}
    rows = list(csv.DictReader(open(REFERENZ / "ratswahl-2021-wahlbereiche.csv", encoding="utf-8-sig"), delimiter=";"))
    lists = []
    for r in rows:
        d = int(r["gebiet-nr"])
        for i, name in label.items():
            cands = {}
            k = 1
            while f"D{i}_{k}" in r:
                if r[f"D{i}_{k}"] != "":
                    cands[k] = int(r[f"D{i}_{k}"])
                k += 1
            total = int(r[f"D{i}_summe_liste_kandidaten"] or 0)
            lv = r[f"D{i}_liste"]
            lists.append(DistrictList(name, d, total, int(lv) if lv != "" else None, cands or None, len(cands)))
    return lists, meta


def test_zuteilung_reproduziert_das_amtliche_ergebnis_2021():
    lists, meta = _listen_2021()
    a = allocate(lists, meta["sitze_gesamt"])
    assert {p: s for p, s in a.seats_by_party.items() if s} == {
        "GRÜNE": 16, "SPD": 15, "CDU": 9, "DIE LINKE.": 4, "FDP": 3, "AfD": 1, "PIRATEN": 1, "Volt": 1,
    }
    meins = {(m.party, m.district, m.votes, "direkt" if m.kind == "direct" else f"Listenplatz {m.position}") for m in a.mandates}
    amtlich = {(s["party"], s["district"], s["votes"], s["kind"]) for s in meta["sitzverteilung"]}
    assert meins == amtlich
    assert a.ties == [] and a.vacant == 0


def test_abstaende_2021():
    lists, meta = _listen_2021()
    # Volts einziger Sitz kam über die Liste (Platz 1, 213 Stimmen). Platz 2
    # (201 Stimmen) hätte 402 mehr gebraucht, dann wäre es ein Personensitz.
    assert votes_to_seat(lists, 50, "Volt", 1, 1, 20000) == 0
    assert votes_to_seat(lists, 50, "Volt", 1, 2, 20000) == 402
    gewinn, verlust = party_seat_margins(lists, 50, "Volt", 50000)
    assert gewinn == 619 and verlust == 3699
    assert votes_to_seat(lists, 50, "Volt", 1, 2, 100) is None


def test_ueberhang_wandert_in_andere_wahlbereiche():
    """§ 37 Abs. 5: mehr Sitze als Bewerber*innen — die Sitze gehen an die
    stimmenstärksten nicht Gewählten derselben Partei anderswo."""
    lists = [
        DistrictList("A", 1, 9000, 9000, {1: 0}, 1),
        DistrictList("A", 2, 1000, 0, {1: 700, 2: 300}, 2),
        DistrictList("B", 1, 100, 100, {1: 0}, 3),
    ]
    a = allocate(lists, 4)
    assert a.seats_by_party == {"A": 4, "B": 0}
    kinds = sorted((m.district, m.position, m.kind) for m in a.mandates)
    assert kinds == [(1, 1, "list"), (2, 1, "direct"), (2, 2, "transfer")] or a.vacant == 1


def test_ohne_personenstimmen_gibt_es_sitze_aber_keine_namen():
    lists = [DistrictList("A", 1, 700, None, None, 10), DistrictList("B", 1, 300, None, None, 10)]
    a = allocate(lists, 10)
    assert a.seats_by_party == {"A": 7, "B": 3}
    assert all(m.kind == "unknown" and m.position is None for m in a.mandates) and len(a.mandates) == 10
    # Mit drei Bewerber*innen je Liste greift § 37 Abs. 5 / § 36 Abs. 7: Der
    # Rest bleibt unbesetzt, weil es keine anderen Wahlbereiche gibt.
    knapp = [DistrictList("A", 1, 700, None, None, 3), DistrictList("B", 1, 300, None, None, 3)]
    assert allocate(knapp, 10).vacant == 4


# ------------------------------------------------------------------ Register

def test_register_passt_zu_den_csv_spalten_2026():
    """Die Reihenfolge der Wahlvorschläge in der Bekanntmachung ist die der
    Spalten D1…D16 — je Liste stimmt die Höchstzahl an Bewerber*innen mit den
    Kandidatenspalten der CSV überein."""
    reg = register.load()
    kopf = (FIXTURES / "2026-wahlbereiche.csv").read_text(encoding="utf-8-sig").splitlines()[0].split(";")
    spalten: dict[int, int] = {}
    for h in kopf:
        if "_2_" in h and h.startswith("D"):
            n, k = h[1:].split("_2_")
            spalten[int(n)] = max(spalten.get(int(n), 0), int(k))
    for p in reg.parties:
        maximum = max(len(c) for c in p.areas.values())
        if p.kind == "einzelbewerber":
            assert p.index not in spalten, "ein Einzelwahlvorschlag hat keine Kandidatenspalten"
        else:
            assert spalten.get(p.index) == maximum, (p.slug, p.index, spalten.get(p.index), maximum)
    assert sum(p.candidates_total for p in reg.parties) == 383
    assert len(reg.parties) == 16 and reg.seats == 52
    assert all(set(p.areas) <= {1, 2, 3, 4, 5, 6} for p in reg.parties)
    for p in reg.parties:
        for cs in p.areas.values():
            assert [c.position for c in cs] == list(range(1, len(cs) + 1))
            assert all(", " in c.name and c.born for c in cs)


def test_register_ist_aus_der_bekanntmachung_erzeugt():
    """``kommunalwahl/kandidaten.py --pruefen`` — die eingecheckte Datei ist
    der Stand des Skripts, nicht von Hand nachbearbeitet."""
    pytest.importorskip("pypdf")
    sys.path.insert(0, str(WURZEL / "kommunalwahl"))
    import kandidaten

    erzeugt = json.dumps(kandidaten.lies(), ensure_ascii=False, indent=1) + "\n"
    assert erzeugt == KANDIDATEN.read_text(encoding="utf-8"), "python3 kommunalwahl/kandidaten.py ausführen"


# ------------------------------------------------------------------ Votemanager

def test_csv_schema_2026_und_2021():
    rows = votemanager.parse((FIXTURES / "2026-wahlbereiche.csv").read_text(encoding="utf-8"))
    assert [r.number for r in rows] == [1, 2, 3, 4, 5, 6]
    assert rows[0].reports_expected == 22 and rows[0].reports_received == 0 and not rows[0].counted
    assert rows[0].lists[7].total is None and rows[0].lists[7].candidates is None
    assert 11 in rows[0].lists  # Einzelwahlvorschlag: nur D11_4
    alt = votemanager.parse((REFERENZ / "ratswahl-2021-wahlbereiche.csv").read_text(encoding="utf-8-sig"))
    assert alt[0].number == 1 and alt[0].counted and alt[0].valid_votes == 35859
    assert alt[0].lists[1].total == 8993 and alt[0].lists[1].list_votes == 4435 and alt[0].lists[1].candidates[1] == 1868


def test_wahlbezirk_zu_wahlbereich_2021():
    """Die Nummernregel (1xx…6xx, 9x0…9x6) trifft alle 133 Bezirke: Die Summen
    je Wahlbereich ergeben genau die Wahlbereichs-Zeilen."""
    bezirke = votemanager.parse((REFERENZ / "ratswahl-2021-wahlbezirke.csv").read_text(encoding="utf-8-sig"))
    bereiche = votemanager.parse((REFERENZ / "ratswahl-2021-wahlbereiche.csv").read_text(encoding="utf-8-sig"))
    assert len(bezirke) == 133
    summen: dict[int, int] = {}
    for b in bezirke:
        n = votemanager.district_number(b.name, None)
        a = votemanager.area_of_district(n)
        assert a in (1, 2, 3, 4, 5, 6), b.name
        summen[a] = summen.get(a, 0) + (b.valid_votes or 0)
    assert summen == {r.number: r.valid_votes for r in bereiche}


# ------------------------------------------------------------------ Hochrechnung

def test_hochrechnung_trifft_das_endergebnis_wenn_die_referenz_die_wahrheit_ist():
    reg, ref = register.load(), reference.load()
    voll = service.compose(reg, ref, service.probe_snapshot(reg, ref, None), "probe")
    teil = service.compose(reg, ref, service.probe_snapshot(reg, ref, 60), "probe")
    assert voll["phase"] == "complete" and teil["phase"] == "counting"
    assert sum(p["seats"] or 0 for p in voll["parties"]) == 52
    assert {p["slug"]: p["projected_seats"] for p in teil["parties"]} == {p["slug"]: p["seats"] for p in voll["parties"]}
    for a_teil, a_voll in zip(teil["areas"], voll["areas"]):
        assert [(p["slug"], p["projected_seats"]) for p in a_teil["parties"]] == [(p["slug"], p["seats"]) for p in a_voll["parties"]]
    assert voll["mandates"] == voll["projected_mandates"] and len(voll["mandates"]) == 52
    assert all(m["name"] for m in voll["mandates"])
    volt = next(p for p in voll["parties"] if p["slug"] == "volt")
    assert volt["seats"] == 1 and volt["seats_2021"] == 1 and volt["share_2021_pct"] == 2.63


def test_hochrechnung_ohne_ausgezaehlte_bezirke_ist_keine():
    rows = votemanager.parse((FIXTURES / "2026-wahlbezirk.csv").read_text(encoding="utf-8"))
    assert project({}, rows, [], [1]) is None


# ------------------------------------------------------------------ Endpunkt

@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    service.reset()
    yield TestClient(app)
    service.reset()


def test_endpunkt_ist_hinter_dem_schalter(client, monkeypatch):
    monkeypatch.delenv("FEATURE_FLAGS", raising=False)
    assert client.get("/api/wahlabend").status_code == 404
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    r = client.get("/api/wahlabend?probe=2021&counted=40")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["dataset"] == "probe" and d["phase"] == "counting" and d["progress"] == {"districts_total": 133, "districts_counted": 40}
    assert {a["number"] for a in d["areas"]} == {1, 2, 3, 4, 5, 6}
    assert len(d["mandates"]) == 52 and d["election"]["seats"] == 52


def test_endpunkt_live_vor_der_auszaehlung_und_bei_netzfehler(client, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    from datetime import datetime, timezone

    def leer(force: bool = False):
        return votemanager.Snapshot(
            votemanager.parse((FIXTURES / "2026-stadt.csv").read_text(encoding="utf-8")),
            votemanager.parse((FIXTURES / "2026-wahlbereiche.csv").read_text(encoding="utf-8")),
            votemanager.parse((FIXTURES / "2026-wahlbezirk.csv").read_text(encoding="utf-8")),
            datetime.now(timezone.utc), "Mon, 31 Aug 2026 10:54:31 GMT", True, None,
        )

    monkeypatch.setattr(votemanager, "fetch", leer)
    d = client.get("/api/wahlabend").json()
    assert d["dataset"] == "live" and d["phase"] == "before" and d["person_votes_available"] is False
    assert d["progress"] == {"districts_total": 133, "districts_counted": 0}
    assert all(p["seats"] is None and p["votes"] is None for p in d["parties"])
    assert d["mandates"] == [] and d["source"]["ok"] is True
    volt = next(p for p in d["parties"] if p["slug"] == "volt")
    assert volt["candidates_total"] == 13 and volt["color"].startswith("#")

    service.reset()

    def kaputt(force: bool = False):
        return votemanager.Snapshot([], [], [], datetime.now(timezone.utc), None, False, "ConnectionError: zu")

    monkeypatch.setattr(votemanager, "fetch", kaputt)
    d = client.get("/api/wahlabend").json()
    assert d["source"]["ok"] is False and "ConnectionError" in d["source"]["error"]
    assert d["phase"] == "before" and len(d["areas"]) == 6
