"""Die Quartalsberichte der Beteiligungen (council/holding_quarterly.py).

Die Fixtures sind Auszüge aus den echten Anlagentexten (Tabellen und der Anfang
jedes Unternehmensabschnitts), keine erfundenen Zeilen:

* ``quartalsbericht_26_0124.txt`` — Bericht zum 31.12.2025: Tabelle gegen
  Seitentext (Klinikum 77 €, WEH 3 €, AWB 1 €), geänderter Plan (BBGO, VWG,
  SOG), Gesamtzuschussbedarf der VWG.
* ``quartalsbericht_21_0578.txt`` — 30.06.2021: Trennstriche U+2010, „€“ in der
  Tabellenzelle, „(geänderter) Plan“.
* ``quartalsbericht_19_0148.txt`` — 31.12.2018: TEUR, gerundet, die Abweichung
  als Plan − HR.
* ``quartalsbericht_25_0043.txt`` — 31.12.2024: SOG ohne Vorjahr (drei Zahlen).
* ``quartalsbericht_21_0124.txt`` — 31.12.2020: EGH, Hochrechnung in Tabelle
  und Seitentext verschieden.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from council import finanzquellen, herkunft, holding_quarterly as hq
from council.store import CouncilStore

FIX = Path(__file__).resolve().parent / "fixtures"
TITEL = "Bericht zum {q}. Quartal{j} der städtischen Beteiligungsunternehmen und Eigenbetriebe - Bericht"


def _text(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _lies(name: str, q: int, jahr: int | None, nr: str) -> hq.Bericht:
    return hq.lies_bericht(_text(name), TITEL.format(q=q, j=f" {jahr}" if jahr else ""), nr, 1)


@pytest.fixture(scope="module")
def q4_2025() -> hq.Bericht:
    return _lies("quartalsbericht_26_0124.txt", 4, 2025, "26/0124")


def _zeile(bericht: hq.Bericht, firma: str) -> hq.Zeile:
    return next(z for z in bericht.zeilen if z.company == firma)


# --- Bericht zum 31.12.2025 ------------------------------------------------

def test_stichtag_einheit_und_vorzeichenregel(q4_2025):
    assert (q4_2025.fiscal_year, q4_2025.as_of, q4_2025.quarter) == (2025, "2025-12-31", 4)
    assert (q4_2025.unit, q4_2025.rounded_to) == ("EUR", 1)
    assert q4_2025.sign_rule == "forecast_minus_plan"
    assert len(q4_2025.zeilen) == 11 and not q4_2025.abgewiesen


def test_klinikum_plan_und_hochrechnung_stehen_getrennt(q4_2025):
    z = _zeile(q4_2025, "klinikum")
    assert (z.plan, z.forecast, z.deviation_printed) == (-25_429_193, -23_865_033, 1_564_237)
    # Der Seitentext nennt den Plan mit 77 € Unterschied — beide bleiben stehen.
    assert z.plan_text == -25_429_270 and z.conflict
    assert z.plan_kind == "original"
    assert z.statement == "Der Wirtschaftsplan wird eingehalten."
    # Die Vorjahresspalte ist ein Prüfwert, nirgends ein Ist.
    assert z.prior_reported == -27_801_940


def test_plan_art_je_unternehmen(q4_2025):
    assert _zeile(q4_2025, "bbgo").plan_kind == "adjusted"
    assert _zeile(q4_2025, "stadion").plan_kind == "adjusted"
    assert _zeile(q4_2025, "otm").plan_kind == "original"


def test_vwg_fuehrt_beide_plaene_und_den_zuschussbedarf(q4_2025):
    z = _zeile(q4_2025, "vwg")
    assert z.basis == "subsidy_need"
    assert (z.plan, z.plan_kind) == (-14_972_040, "adjusted")
    assert (z.plan_other, z.plan_other_kind) == (-14_659_040, "original")
    assert not z.conflict


def test_kleine_widersprueche_zwischen_tabelle_und_text_sind_markiert(q4_2025):
    konflikte = {z.company for z in q4_2025.zeilen if z.conflict}
    assert konflikte == {"klinikum", "weh", "awb"}
    assert _zeile(q4_2025, "weh").plan_text == -6_212_495
    assert _zeile(q4_2025, "awb").plan_text == 627_510


def test_eigenbetriebe_aus_teil_b_stehen_mit_drin(q4_2025):
    assert {"awb", "bbo", "egh"} <= {z.company for z in q4_2025.zeilen}
    assert _zeile(q4_2025, "egh").forecast == -5_149_000


def test_proben_der_zeilen_ohne_konflikt_tragen_die_plan_text_probe(q4_2025):
    assert hq.PROBE_PLAN_TEXT in _zeile(q4_2025, "bbgo").probes
    assert hq.PROBE_PLAN_TEXT not in _zeile(q4_2025, "klinikum").probes
    # Herkunft: nur was JEDE Zeile bestanden hat.
    assert hq.PROBE_PLAN_TEXT not in q4_2025.probes
    assert set(q4_2025.probes) == {hq.PROBE_DEVIATION, hq.PROBE_PERIOD}


# --- Format-Eigenheiten ------------------------------------------------------

def test_trennstriche_und_euro_zeichen_2021():
    b = _lies("quartalsbericht_21_0578.txt", 2, 2021, "21/0578")
    assert b.as_of == "2021-06-30" and b.sign_rule == "forecast_minus_plan"
    otm = _zeile(b, "otm")
    assert (otm.plan, otm.forecast) == (-1_150_000, -1_154_240)
    awb = _zeile(b, "awb")   # „288.650 €“ mitten in der Zeile
    assert (awb.plan, awb.forecast, awb.deviation_printed) == (288_650, 360_700, 72_050)


def test_teur_bericht_2018_rechnet_in_euro_und_dreht_das_vorzeichen():
    b = _lies("quartalsbericht_19_0148.txt", 4, None, "19/0148")
    assert (b.unit, b.rounded_to, b.sign_rule) == ("TEUR", 1000, "plan_minus_forecast")
    assert b.fiscal_year == 2018 and b.as_of == "2018-12-31"
    otm = _zeile(b, "otm")
    assert (otm.plan, otm.forecast, otm.deviation_printed) == (-857_000, -817_000, -40_000)
    kol = _zeile(b, "klinikum")   # 1.972 gedruckt, 1.973 gerechnet: Rundung
    assert (kol.plan, kol.forecast) == (-3_147_000, -5_120_000) and not kol.conflict


def test_leere_erste_spalte_ist_eine_zeile_mit_drei_zahlen():
    b = _lies("quartalsbericht_25_0043.txt", 4, 2024, "25/0043")
    sog = _zeile(b, "stadion")
    assert sog.prior_reported is None
    assert (sog.plan, sog.forecast, sog.deviation_printed) == (-190_000, -182_000, 8_000)


def test_hochrechnung_die_im_text_anders_lautet_wird_nicht_gespeichert():
    b = _lies("quartalsbericht_21_0124.txt", 4, 2020, "21/0124")
    assert "egh" not in {z.company for z in b.zeilen}
    assert any("EGH" in s and "Seitentext" in s for s in b.abgewiesen)
    assert {"klinikum", "bbgo", "awb"} <= {z.company for z in b.zeilen}


def test_verlorenes_minus_zeichen_reisst_die_abweichungsprobe():
    text = _text("quartalsbericht_26_0124.txt").replace("-6.247.913", "6.247.913", 1)
    b = hq.lies_bericht(text, TITEL.format(q=4, j=" 2025"), "26/0124", 1)
    assert "bbgo" not in {z.company for z in b.zeilen}
    assert any(s.startswith("BBGO: gedruckte Abweichung") for s in b.abgewiesen)
    assert len(b.zeilen) == 10


# --- Ganzer Bericht fällt durch ---------------------------------------------

def test_stichtag_im_titel_gegen_text():
    with pytest.raises(hq.QuartalFehler, match="Stichtag"):
        hq.lies_bericht(_text("quartalsbericht_26_0124.txt"),
                        TITEL.format(q=3, j=" 2025"), "26/0124")


def test_jahr_im_titel_gegen_tabelle():
    with pytest.raises(hq.QuartalFehler, match="Titel nennt"):
        hq.lies_bericht(_text("quartalsbericht_26_0124.txt"),
                        TITEL.format(q=4, j=" 2024"), "26/0124")


def test_text_ohne_tabelle():
    with pytest.raises(hq.QuartalFehler, match="Übersichtstabelle"):
        hq.lies_bericht("Der Bericht wird zur Kenntnis genommen.", TITEL.format(q=4, j=" 2025"), "x")


def test_vorzeichenregel_nicht_bestimmbar():
    kopf = ("2024 Ist 2025 Plan 2025 HR Abweichung Plan/HR [Euro] [Euro] [Euro] [Euro] ")
    zeilen = "BBGO -1 -100 -50 777 KOL -1 -100 -50 888"
    with pytest.raises(hq.QuartalFehler):
        hq.lies_bericht(kopf + zeilen, TITEL.format(q=4, j=" 2025"), "x")


# --- Hilfsfunktionen ---------------------------------------------------------

@pytest.mark.parametrize("titel,erwartet", [
    ("Bericht zum 4. Quartal 2025 der städtischen Beteiligungsunternehmen und Eigenbetriebe - Bericht", True),
    ("Bericht zum 4. Quartal der städtischen Beteiligungsunternehmen und Eigenbetriebe - Bericht", True),
    ("Bericht zum 2. Quartal 2020 Auswirkungen der Corona-Pandemie", False),
    ("Finanz- und Leistungsbericht zum 30.06.2025", False),
    (None, False),
])
def test_titel_erkennung(titel, erwartet):
    assert hq.ist_quartalsbericht(titel) is erwartet


@pytest.mark.parametrize("label,kopf,erwartet", [
    ("Quartalsbericht 31.12.2025", "", (2025, "2025-12-31")),
    ("Quartalsbericht Q3-2024", "", (2024, "2024-09-30")),
    ("Anlage", "Bericht zum 2. Quartal 2021 der städtischen", (2021, "2021-06-30")),
    ("Anlage", "Bericht zum 4. Quartal der städtischen", None),
    ("Bericht Q2 2025 Endfassung", "", (2025, "2025-06-30")),
])
def test_einheit_aus_kopf(label, kopf, erwartet):
    assert hq.einheit_aus_kopf(label, kopf) == erwartet


def test_jedes_kuerzel_hat_name_und_muster():
    for key in hq.KUERZEL.values():
        assert key in hq.NAMEN and key in hq.FIRMEN, key
    assert hq.firmen_in("hochrechnung klinikum und vwg") == ["klinikum", "vwg"]
    assert hq.firmen_in("wie ist der stand beim stadion") == []


# --- Speichern, Herkunft, Registry -------------------------------------------

def _store(tmp_path) -> CouncilStore:
    return CouncilStore(tmp_path / "c.sqlite")


def test_speichern_ersetzt_nur_den_eigenen_stichtag(tmp_path, q4_2025):
    store = _store(tmp_path)
    try:
        q2 = _lies("quartalsbericht_21_0578.txt", 2, 2021, "21/0578")
        for b in (q4_2025, q2):
            store.save_holding_forecasts(b, hq.herkunft_fuer(
                b, document_id=1, label="Quartalsbericht", url="https://example.org/x"))
        assert not store.herkunft_luecken()
        assert (2025, "2025-12-31") in store.holding_forecast_einheiten()
        assert (2021, "2021-06-30") in store.holding_forecast_einheiten()
        n = store._conn.execute("SELECT COUNT(*) FROM council_holding_forecasts").fetchone()[0]
        # Zweiter Lauf: kein Wachstum, nichts verdoppelt.
        store.save_holding_forecasts(q4_2025, hq.herkunft_fuer(
            q4_2025, document_id=1, label="Quartalsbericht", url="https://example.org/x"))
        assert store._conn.execute(
            "SELECT COUNT(*) FROM council_holding_forecasts").fetchone()[0] == n
        reihe = store.holding_forecasts("klinikum")
        assert [r["as_of"] for r in reihe] == ["2021-06-30", "2025-12-31"]
        assert reihe[-1]["source_citation"].startswith("Bericht zum 4. Quartal 2025")
    finally:
        store.close()


def test_mehrere_hochrechnungen_eines_jahres_bleiben_nebeneinander(tmp_path):
    store = _store(tmp_path)
    try:
        for nr, q, jahr, name in (("25/0043", 4, 2024, "quartalsbericht_25_0043.txt"),):
            b = _lies(name, q, jahr, nr)
            store.save_holding_forecasts(b, hq.herkunft_fuer(
                b, document_id=2, label="x", url="https://example.org/y"))
        # Ein zweiter Stand desselben Jahres (erfundene Verschiebung des Stichtags).
        b2 = _lies("quartalsbericht_25_0043.txt", 4, 2024, "25/0043")
        b2.as_of, b2.quarter = "2024-09-30", 3
        store.save_holding_forecasts(b2, hq.herkunft_fuer(
            b2, document_id=3, label="y", url="https://example.org/z"))
        stand = [r["as_of"] for r in store.holding_forecasts("otm")]
        assert stand == ["2024-09-30", "2024-12-31"]
    finally:
        store.close()


def test_abgleich_meldet_ohne_nachbartabellen_nichts(tmp_path, q4_2025):
    store = _store(tmp_path)
    try:
        assert hq.abgleich(q4_2025, store._conn) == []
    finally:
        store.close()


def test_abgleich_bestaetigt_den_wirtschaftsplan_und_meldet_abstand(tmp_path, q4_2025):
    store = _store(tmp_path)
    try:
        store._conn.execute(
            "INSERT INTO council_business_plans (enterprise, year, enterprise_name, "
            "template_number, result, probes, fetched_at) VALUES (?,?,?,?,?,?,?)",
            ("bbgo", 2025, "BBGO", "25/0614", -6_247_913.0, "x", "2026-01-01"))
        store._conn.execute(
            "INSERT INTO council_company_accounts (company, year, indicator, value, unit, "
            "report_year, probes, fetched_at) VALUES (?,?,?,?,?,?,?,?)",
            ("bbgo", 2024, "jahresergebnis", -5_709_452.79, "eur", 2024, "x", "2026-01-01"))
        befund = dict((t, s) for s, t in hq.abgleich(q4_2025, store._conn))
        assert any("= Wirtschaftsplan 2025" in t for t in befund)
        assert any("Vorjahr -5.709.453 € = Abschluss 2024" in t for t in befund)
    finally:
        store.close()


def test_registry_fuehrt_die_neue_quelle():
    q = finanzquellen.QUELLEN["holding_quarterly"]
    assert q.tabelle == "council_holding_forecasts" and q.unit == "Stichtag"
    assert "holding_quarterly" in finanzquellen.REIHENFOLGE
    assert "council_holding_forecasts" in herkunft.HERKUNFT_TABELLEN
    assert q.lauf == ("scripts/ingest_holding_quarterly.py",)
    assert q.erkennung and q.erkennung.vorlagen_muster == (hq.TITEL_MUSTER,)
    for probe in (hq.PROBE_DEVIATION, hq.PROBE_PERIOD, hq.PROBE_PLAN_TEXT):
        assert probe in herkunft.PROBEN


# --- Der Ingest, Ende zu Ende ------------------------------------------------

def _bestand(store: CouncilStore) -> None:
    c = store._conn
    c.execute("INSERT INTO council_templates (kvonr, template_number, title, fetched_at) "
              "VALUES (1, '26/0124', ?, '2026-01-01')", (TITEL.format(q=4, j=" 2025"),))
    c.execute("INSERT INTO council_attachments (document_id, kvonr, label, url, raw_text, status, "
              "fetched_at) VALUES (304363, 1, 'Quartalsbericht 31.12.2025', "
              "'https://example.org/304363', ?, 'ok', '2026-01-01')",
              (_text("quartalsbericht_26_0124.txt"),))
    c.commit()


def test_ingest_trockenlauf_und_lauf(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ingest_holding_quarterly",
        Path(__file__).resolve().parents[1] / "scripts" / "ingest_holding_quarterly.py")
    ingest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ingest)

    db = tmp_path / "c.sqlite"
    store = CouncilStore(db)
    _bestand(store)
    store.close()

    trocken = ingest.main(["--trockenlauf", "--db", str(db)])
    assert trocken["gelesen"] == 1 and trocken["zeilen"] == 11 and trocken["trocken"] == 1
    store = CouncilStore(db)
    assert store.holding_forecast_einheiten() == set()
    store.close()

    echt = ingest.main(["--db", str(db)])
    assert echt["gespeichert"] == 11 and echt["abgewiesen"] == 0 and echt["konflikte"] == 3
    store = CouncilStore(db)
    try:
        assert store.holding_forecast_einheiten() == {(2025, "2025-12-31")}
    finally:
        store.close()

    # --nur-fehlende liest nichts noch einmal.
    nochmal = ingest.main(["--nur-fehlende", "--db", str(db)])
    assert nochmal["gelesen"] == 0
    # Und eine Anlage ohne Text ist kein Absturz.
    store = CouncilStore(db)
    store._conn.execute("UPDATE council_attachments SET raw_text = NULL")
    store._conn.commit()
    store.close()
    assert ingest.main(["--trockenlauf", "--db", str(db)])["ohne_text"] == 1


def test_leere_tabelle_kommt_nicht_aus_der_sqlite_hoelle(tmp_path):
    store = _store(tmp_path)
    try:
        assert store.holding_forecasts() == []
        assert store.holding_forecast_einheiten() == set()
        with pytest.raises(sqlite3.OperationalError):
            store._conn.execute("SELECT nope FROM council_holding_forecasts")
    finally:
        store.close()
