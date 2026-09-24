"""Die Schulden der acht kreisfreien Städte (council/regionalstatistik.py).

``fixtures/regionalstatistik_71327.json`` sind echte Zeilen der Tabellen
71327-Z-02 (Schulden, Kreisschlüssel „F03403") und 71327-Z-07 (Einwohner,
Regionalschlüssel „F03403000000000") für 2022 und 2023, abgerufen am
24.09.2026, dazu Zeilen des Landkreises Oldenburg, die NICHT zur Stadt
gehören dürfen.
"""
import json
import sys
from pathlib import Path

from council import regionalstatistik as rs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

FIX = json.loads((Path(__file__).parent / "fixtures" / "regionalstatistik_71327.json")
                 .read_text(encoding="utf-8"))


def _lesung() -> rs.Lesung:
    return rs.lies(FIX["schulden"], FIX["einwohner"])


def test_beide_schluesselformen_werden_der_stadt_zugeordnet():
    l = _lesung()
    assert l.werte[("03403000", 2023, "debt_core")] == 46_577_118
    assert l.werte[("03403000", 2023, "debt_entities")] > 300_000_000
    assert 170_000 < l.werte[("03403000", 2023, "population")] < 180_000
    assert {k for (k, _, _) in l.werte} == {key for key, _ in rs.STAEDTE.values()}


def test_landkreis_gleichen_namens_und_teilschluessel_zaehlen_nicht():
    assert rs._stadt("F03403") == ("03403000", "Oldenburg")
    assert rs._stadt("F03403000000000") == ("03403000", "Oldenburg")
    assert rs._stadt("F03458") is None                 # Landkreis Oldenburg
    assert rs._stadt("F03403000001") is None           # ein Teil, nicht die Stadt
    assert "F03458" in FIX["schulden"]                 # steht in der Datei …
    assert all(k in {key for key, _ in rs.STAEDTE.values()} for (k, _, _) in _lesung().werte)


def test_probe_gegen_die_eigene_schuldenreihe():
    l = rs.pruefe(_lesung(), {2023: 46_577_000})       # eigene Reihe in T€
    assert l.bestanden == {2023}
    assert l.hinweise == ["2022: keine eigene Reihe zum Prüfen"]
    l = rs.pruefe(_lesung(), {2023: 47_000_000, 2022: 49_700_000})
    assert l.bestanden == set()
    assert any("2023: Statistik" in h for h in l.hinweise)


def test_leere_tabellen_sind_ein_fehler():
    kopf = FIX["schulden"].splitlines()[0] + "\n"
    try:
        rs.lies(kopf, kopf)
    except rs.RegionalFehler:
        return
    raise AssertionError("keine Städte, aber kein Fehler")


def test_endpunkt_je_einwohner_alphabetisch(tmp_path):
    from council import herkunft
    from council.store import CouncilStore
    from app.routers.council import haushalt_schuldenvergleich, haushalt_vergleich

    store = CouncilStore(tmp_path / "c.sqlite")
    try:
        l = rs.pruefe(_lesung(), {2023: 46_577_000})
        namen = dict(rs.STAEDTE.values())
        zeilen = [{"year": j, "key": k, "city": namen[k], "indicator": i, "value": v,
                   "unit": "count" if i == "population" else "eur"}
                  for (k, j, i), v in l.werte.items() if j in l.bestanden]
        store.save_staedtevergleich(rs.SERIES, zeilen, herkunft.Herkunft(
            kind="regionalstatistik", probe=[rs.PROBE], url="https://x", label="71327"))
        a = haushalt_schuldenvergleich(_user={}, store=store)
        assert [y["year"] for y in a["years"]] == [2023]
        staedte = a["years"][0]["cities"]
        assert [c["city"] for c in staedte] == sorted(namen.values())
        ol = next(c for c in staedte if c["is_oldenburg"])
        assert ol["core_per_capita"] == round(46_577_118 / ol["population"], 2)
        assert all("rank" not in c for c in staedte)
        assert all(v["series"] != rs.SERIES for v in haushalt_vergleich(_user={}, store=store)["values"])
    finally:
        store.close()


def test_eigene_reihe_springt_auf_die_schuldenuebersicht_im_plan():
    """2022 geht die Jahrbuch-Tabelle nicht auf, die Aufteilung ist verworfen —
    die Schuldenübersicht im Plan 2024 (Stand 31.12.2022) springt ein. Wo das
    Jahrbuch einen Wert hat, gilt der."""
    schulden = [{"year": 2021, "credit_market": 53_074_000.0},
                {"year": 2022, "credit_market": None},
                {"year": 2023, "credit_market": 46_577_000.0}]
    plan = [{"budget_year": 2024, "entity": "Kernhaushalt", "code": "1.2", "start_prior": 49_740_000.0},
            {"budget_year": 2024, "entity": "Kernhaushalt", "code": "1.3", "start_prior": 1.0},
            {"budget_year": 2025, "entity": "Kernhaushalt", "code": "1.2", "start_prior": 99.0},
            {"budget_year": 2024, "entity": "Eigenbetrieb Gebäudewirtschaft und Hochbau",
             "code": "1.2", "start_prior": 7.0}]
    assert rs.eigene_reihe(schulden, plan) == {2021: 53_074_000.0, 2022: 49_740_000.0,
                                               2023: 46_577_000.0}
