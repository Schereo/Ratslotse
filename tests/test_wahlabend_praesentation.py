"""Der Ersatzpfad: die Ergebnisdarstellung des Votemanagers statt der CSVs.

Die Fixtures sind die echten JSON-Dateien der Ratswahl 2021 vom selben
Votemanager (``tests/fixtures/wahlabend/praesentation-2021/``). Die harte
Zusage: Aus ihnen entstehen **dieselben** Zeilen wie aus der CSV von 2021 —
je Wahlbereich, je Liste, je Listenplatz — und damit dieselben 50 Mandate.
Alles Weitere (Namen, die niemand zuordnen kann; leere Dateien vor der
Auszählung; die Sitzverteilung des Votemanagers als Gegenprobe) sind die
Ränder, an denen der Ersatz sich vom Hauptweg unterscheidet.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))
# Wegwerf-Datenbanken und die übrigen Testwerte kommen aus
# `tests/conftest.py` — dort EINMAL je Prozess gesetzt, damit sie nicht an
# der Import-Reihenfolge der Module hängen (siehe die Begründung dort).

from app.election import presentation, register, service, votemanager  # noqa: E402
from app.election.seats import Allocation, DistrictList, allocate  # noqa: E402

REFERENZ = WURZEL / "kommunalwahl" / "referenz-2021"
FIXTURES = WURZEL / "tests" / "fixtures" / "wahlabend" / "praesentation-2021"


def _json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _meta() -> dict:
    return json.loads((REFERENZ / "ratswahl-2021.json").read_text(encoding="utf-8"))


def _resolver_2021():
    """2021 kannte das Register von 2026 noch nicht: Label -> Spaltenindex
    aus der Referenzdatei, exakt."""
    by_label = {p["label"]: int(p["index"]) for p in _meta()["parteien"]}
    return lambda name: by_label.get(name)


def _rows_2021() -> dict[int, votemanager.AreaRow]:
    """Die sechs Wahlbereiche aus der Ergebnisdarstellung als ``AreaRow``."""
    resolve = _resolver_2021()
    out: dict[int, votemanager.AreaRow] = {}
    for label, gid in presentation.area_links(_json("uebersicht-wahlbereiche.json")):
        number = votemanager._area_number(label, None)
        if number is None:
            continue
        area = presentation.parse_area(_json(f"wahlbereich-{number}.json"))
        assert area is not None, label
        row, why = votemanager.row_from_presentation(area, label, number, resolve)
        assert row is not None and why == [], (label, why)
        out[number] = row
    return out


# ------------------------------------------------------------------ Struktur

def test_uebersicht_nennt_die_sechs_wahlbereiche_und_die_stadt():
    links = presentation.area_links(_json("uebersicht-wahlbereiche.json"))
    assert [gid for _, gid in links] == [f"ebene_5_id_{n}" for n in range(1235, 1241)] + ["ebene_3_id_513"]
    assert [votemanager._area_number(label, None) for label, _ in links] == [1, 2, 3, 4, 5, 6, None]


def test_wahl_json_nennt_stadt_und_wahlbereichsebene():
    assert presentation.ids_of(_json("wahl.json")) == ("ebene_3_id_513", "ebene_5")
    # 2026 heißen die Ebenen anders — die Form ist dieselbe.
    wahl_2026 = {"menu_links": [{"id": "ebene_-6361_id_10358", "type": "ergebnis", "title": "Stadt Oldenburg"},
                                {"id": "ebene_-6362", "type": "uebersicht", "title": "Wahlbereiche"},
                                {"id": "ebene_6", "type": "uebersicht", "title": "Wahlbezirke"}]}
    assert presentation.ids_of(wahl_2026) == ("ebene_-6361_id_10358", "ebene_-6362")
    assert presentation.ids_of({"file_version": "26.08.03"}) == (None, None)


def test_vor_der_auszaehlung_ist_nichts_da():
    """So sehen die Dateien von 2026 am Nachmittag aus: nur ein Zeitstempel."""
    leer = {"zeitstempel": "31.08.2026 12:54", "file_version": "26.08.03"}
    assert presentation.parse_area(leer) is None
    assert presentation.area_links(leer) == []
    assert presentation.parse_area("<html>") is None and presentation.area_links(None) == []


def test_zahlen_mit_tausenderpunkt():
    assert presentation.parse_number("1.868") == 1868
    assert presentation.parse_number("210.447") == 210447
    assert presentation.parse_number("46") == 46
    assert presentation.parse_number("") is None and presentation.parse_number(None) is None
    assert presentation.parse_number("5,03 %") is None
    assert presentation.parse_number(12) == 12 and presentation.parse_number(True) is None


# ------------------------------------------------------------------ Dieselben Zeilen wie die CSV

def test_wahlbereiche_aus_der_darstellung_gleichen_der_csv_2021():
    """Je Wahlbereich, je Liste, je Listenplatz dieselbe Zahl wie in der
    Open-Data-CSV — das ist die Zusage, an der der ganze Ersatz hängt: Die
    Unterzeilen der Kandidat*innen stehen in Listenreihenfolge."""
    csv_rows = {r.number: r for r in votemanager.parse(
        (REFERENZ / "ratswahl-2021-wahlbereiche.csv").read_text(encoding="utf-8-sig"))}
    json_rows = _rows_2021()
    assert sorted(json_rows) == [1, 2, 3, 4, 5, 6] == sorted(csv_rows)
    for n, mine in json_rows.items():
        theirs = csv_rows[n]
        assert (mine.reports_expected, mine.reports_received) == (theirs.reports_expected, theirs.reports_received), n
        for f in ("eligible", "voters", "invalid_ballots", "valid_ballots", "valid_votes"):
            assert getattr(mine, f) == getattr(theirs, f), (n, f)
        # Eine Liste, die im Wahlbereich nicht antritt, fehlt in der Darstellung
        # und steht in der CSV mit leeren Spalten — beides heißt „nicht da".
        angetreten = {i for i, lr in theirs.lists.items() if lr.total is not None}
        assert set(mine.lists) == angetreten, n
        for i, lr in mine.lists.items():
            ref = theirs.lists[i]
            if lr.list_votes is None and lr.candidate_sum is None:
                # Ein Einzelwahlvorschlag („Hilbert Schoe, Einzelwahlvorschlag
                # Schoe") hat in der Darstellung EINE Zeile. Die CSV von 2021
                # führte ihn noch mit Listen- und Kandidatenspalte, die von
                # 2026 nur noch mit der Gesamtspalte — genau das entsteht hier.
                assert lr.total == ref.total == ref.candidate_sum and ref.candidates == {1: ref.total}, (n, i)
                continue
            assert (lr.total, lr.list_votes, lr.candidate_sum) == (ref.total, ref.list_votes, ref.candidate_sum), (n, i)
            assert lr.candidates == ref.candidates, (n, i)


def test_zuteilung_aus_der_darstellung_reproduziert_das_amtliche_ergebnis_2021():
    meta = _meta()
    label = {int(p["index"]): p["label"] for p in meta["parteien"]}
    lists = []
    for n, row in sorted(_rows_2021().items()):
        for i, lr in row.lists.items():
            cands = lr.candidates or {}
            lists.append(DistrictList(label[i], n, lr.total or 0, lr.list_votes, cands or None, len(cands)))
    a = allocate(lists, meta["sitze_gesamt"])
    meins = {(m.party, m.district, m.votes, "direkt" if m.kind == "direct" else f"Listenplatz {m.position}") for m in a.mandates}
    amtlich = {(s["party"], s["district"], s["votes"], s["kind"]) for s in meta["sitzverteilung"]}
    assert meins == amtlich and a.ties == [] and a.vacant == 0


def test_stadt_traegt_die_sitzverteilung_des_votemanagers():
    stadt = presentation.parse_area(_json("stadt.json"))
    assert stadt is not None and stadt.counted
    assert (stadt.reports_expected, stadt.reports_received) == (133, 133)
    assert (stadt.eligible, stadt.voters, stadt.valid_votes) == (135173, 72723, 210447)
    assert stadt.official_seats == {"DIE LINKE.": 4, "SPD": 15, "GRÜNE": 16, "FDP": 3, "PIRATEN": 1,
                                    "Volt": 1, "CDU": 9, "AfD": 1}
    # Die Stadt-Tabelle führt alle 72 SPD-Bewerber*innen der sechs Wahlbereiche
    # hintereinander — brauchbar als Summe, nicht als Listenplatz.
    spd = next(l for l in stadt.lists if l.name == "SPD")
    assert (spd.total, spd.list_votes, spd.candidate_sum) == (61032, 31312, 29720)
    assert spd.candidates is not None and len(spd.candidates) == 72 and sum(spd.candidates) == 29720


# ------------------------------------------------------------------ Zuordnung zum Register 2026

def test_namen_des_votemanagers_treffen_das_register_2026():
    resolve = presentation.resolver(register.load())
    reg = register.load()
    assert resolve("GRÜNE") == reg.by_slug("gruene").index
    assert resolve("DIE LINKE.") == reg.by_slug("linke").index
    assert resolve("WFO") == reg.by_slug("fuer-oldenburg").index
    assert resolve("Stille, Einzelwahlvorschlag Stille") == reg.by_slug("stille").index
    # 2021 gab es dieBasis; 2026 nicht — und ein Name, der zu keiner Liste passt,
    # wird nicht geraten.
    assert resolve("dieBasis LV Niedersachsen") is None
    assert resolve("") is None


def test_unbekannte_liste_verwirft_den_ganzen_wahlbereich():
    """Halb ist schlechter als gar nicht: Eine fehlende Liste zählte in der
    Zuteilung als null Stimmen, und das sähe aus wie ein Ergebnis."""
    area = presentation.parse_area(_json("wahlbereich-1.json"))
    assert area is not None
    row, why = votemanager.row_from_presentation(area, "I - Stadtmitte Nord", 1, presentation.resolver(register.load()))
    assert row is None
    assert len(why) == 1 and "dieBasis" in why[0] and "außen vor" in why[0]

    # Zwei Namen auf derselben Spalte — genauso ein Grund.
    doppelt = votemanager.row_from_presentation(area, "I", 1, lambda name: 1)
    assert doppelt[0] is None and "dieselbe Spalte" in doppelt[1][0]


def test_personenstimmen_liegen_erst_vor_wenn_jede_zeile_eine_zahl_traegt():
    payload = _json("wahlbereich-1.json")
    zeilen = payload["Komponente"]["tabelle"]["zeilen"]
    spd = next(z for z in zeilen if z["label"]["labelKurz"] == "SPD - Summe Kandidaten-Stimmen")
    spd["sub_zeilen"][3]["zahl"] = ""
    area = presentation.parse_area(payload)
    assert area is not None
    assert next(l for l in area.lists if l.name == "SPD").candidates is None
    assert next(l for l in area.lists if l.name == "CDU").candidates is not None


def test_einzelwahlvorschlag_hat_nur_eine_zeile():
    payload = {"Komponente": {"tabelle": {"zeilen": [
        {"label": {"labelKurz": "Wahlberechtigte"}, "zahl": "1.000"},
        {"label": {"labelKurz": "SPD - Summe Partei- und Kandidaten-Stimmen"}, "zahl": "300"},
        {"label": {"labelKurz": "SPD - Stimmen für die Partei"}, "zahl": "100"},
        {"label": {"labelKurz": "SPD - Summe Kandidaten-Stimmen"}, "zahl": "200",
         "sub_zeilen": [{"label": {"labelKurz": "A"}, "zahl": "150"}, {"label": {"labelKurz": "B"}, "zahl": "50"}]},
        {"label": {"labelKurz": "Stille, Einzelwahlvorschlag Stille"}, "zahl": "42"},
    ]}, "info": {"titel": "Wahlbereich VI", "hinweis": ["3 von 22 Ergebnissen"],
                 "tabelle": {"zeilen": [{"label": {"labelKurz": "gültige Stimmen"}, "zahl": "342"}]}}}}
    area = presentation.parse_area(payload)
    assert area is not None and area.counted
    assert (area.reports_expected, area.reports_received, area.valid_votes) == (22, 3, 342)
    assert [(l.name, l.total, l.single) for l in area.lists] == [("SPD", 300, False), ("Stille, Einzelwahlvorschlag Stille", 42, True)]
    assert area.lists[0].candidates == (150, 50)


# ------------------------------------------------------------------ Die Gegenprobe der Sitze

def _alloc(seats: dict[str, int]) -> Allocation:
    return Allocation(seats_by_party=seats, seats_by_list={}, mandates=[])


def test_gegenprobe_der_sitzverteilung():
    reg = register.load()
    eigene = {"spd": 15, "gruene": 16, "cdu": 9}
    assert service._official_check(reg, _alloc(eigene), None) == []
    assert service._official_check(reg, _alloc(eigene), {"spd": 15, "gruene": 16}) == []
    hinweise = service._official_check(reg, _alloc(eigene), {"spd": 14, "gruene": 16, "fdp": 1})
    assert len(hinweise) == 1
    assert "SPD 14 statt 15" in hinweise[0] and "FDP 1 statt 0" in hinweise[0] and "GRÜNE" not in hinweise[0]


@pytest.mark.parametrize("name, nummer", [
    ("Wahlbereich IV", 4), ("Wahlbereich 4", 4), ("IV - Nordost", 4), ("Stadt Oldenburg (Oldenburg)", None),
    ("Wahlbereich VI - Südwest", 6),
])
def test_wahlbereichsnummer_aus_dem_label(name, nummer):
    assert votemanager._area_number(name, None) == nummer
