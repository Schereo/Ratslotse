"""Die Jahresabschlüsse der Eigenbetriebe (council/eigenbetriebe_abschluss.py).

Die Fixtures sind echte Ausschnitte aus dem Bestand: die Mehrjahresübersichten
des RPA (EGH 2024/2025, Hafen 2020) und des Wirtschaftsprüfers (AWB 2024), die
einseitige GuV und Bilanz des Bäderbetriebs 2024 und sein Gesamtdokument 2017."""
from __future__ import annotations

import json
from pathlib import Path

from council import eigenbetriebe_abschluss as ea
from council import herkunft as h
from council.store import CouncilStore

FX = json.loads((Path(__file__).parent / "fixtures" / "eigenbetriebe_abschluss.json").read_text())


def _lies(key):
    f = FX[key]
    return ea.lies_dokument(f["text"], f["title"], f["label"], f["document_id"])


def _wert(lesung, year, metric):
    return next(k.value for k in lesung.kennzahlen if k.year == year and k.metric == metric)


def test_mehrjahresuebersicht_egh_mit_fussnoten():
    """Fünf Jahre im Kopf; „Rohertrag 2 31.345 …" und der umgebrochene Cashflow
    mit der Fußnote „3" auf eigener Zeile — die LETZTEN fünf Zahlen gelten."""
    l = _lies("egh_2024")
    assert l.form == "uebersicht"
    assert {k.year for k in l.kennzahlen} == {2020, 2021, 2022, 2023, 2024}
    assert _wert(l, 2024, "revenues") == 66_262_000
    assert _wert(l, 2024, "result") == -2_726_000
    assert _wert(l, 2021, "result") == 2_103_000
    assert _wert(l, 2024, "gross_profit") == 31_345_000
    assert _wert(l, 2024, "cashflow") == 27_593_000
    assert _wert(l, 2024, "investments") == 26_337_000
    assert _wert(l, 2024, "balance_total") == 580_194_000
    assert all(k.metric != "equity_ratio" for k in l.kennzahlen)


def test_mehrjahresuebersicht_hafen_drei_jahre():
    l = _lies("hafen_2020")
    assert {k.year for k in l.kennzahlen} == {2018, 2019, 2020}
    assert _wert(l, 2020, "revenues") == 130_000
    assert _wert(l, 2020, "result") == -229_000
    assert _wert(l, 2018, "investments") == 2_147_000


def test_kennzahlen_awb_mit_einheit_und_beschaeftigten():
    l = _lies("awb_2024")
    assert _wert(l, 2024, "revenues") == 23_824_000
    assert _wert(l, 2024, "result") == 294_000
    assert _wert(l, 2020, "result") == 394_000
    assert _wert(l, 2024, "operating_result") == 154_000
    assert _wert(l, 2024, "financial_result") == 147_000
    besch = next(k for k in l.kennzahlen if k.year == 2024 and k.metric == "employees")
    assert (besch.value, besch.unit) == (180, "Stück")


def test_baederbetrieb_guv_und_bilanz_in_euro():
    g = _lies("bbo_2024_guv")
    assert g.form == "guv+bilanz"
    assert _wert(g, 2024, "revenues") == 2_145_244.92
    assert _wert(g, 2023, "revenues") == 2_137_598.40
    assert _wert(g, 2024, "result") == 0.0
    b = _lies("bbo_2024_bilanz")
    assert _wert(b, 2024, "balance_total") == 56_584_562.72
    assert _wert(b, 2023, "balance_total") == 30_910_732.07
    assert _wert(b, 2024, "equity") == 10_220_112.91


def test_baederbetrieb_2017_vorjahr_in_teur():
    """Bis 2018 steht das Vorjahr ohne Nachkommastellen — in TEUR."""
    l = _lies("bbo_2017")
    assert _wert(l, 2017, "revenues") == 2_030_079.52
    k = next(k for k in l.kennzahlen if k.year == 2016 and k.metric == "revenues")
    assert (k.value, k.unit) == (2_249_000, "TEUR")
    assert _wert(l, 2017, "balance_total") == 24_641_462.90


def test_ueberlappung_bestaetigt_und_widerspricht():
    """EGH 2024 steht im Bericht 2024 (Geschäftsjahr) und 2025 (Vorjahr) —
    zwei Zeugen. Ein abweichender dritter wird gemeldet, der jüngste gilt."""
    alle = _lies("egh_2024").kennzahlen + _lies("egh_2025").kennzahlen
    zeilen, strittig = ea.zusammenfuehren(alle)
    z = next(z for z in zeilen if z["year"] == 2024 and z["metric"] == "revenues")
    assert (z["report_year"], z["confirmations"], z["conflicts"]) == (2025, 2, 0)
    assert ea.PROBE_UEBERLAPPUNG in z["probes"]
    assert not strittig
    falsch = ea.Kennzahl("egh", 2024, "revenues", 60_000_000, "TEUR", 2026, 1, "x", ea.PROBE_SPALTEN)
    zeilen, strittig = ea.zusammenfuehren(alle + [falsch])
    z = next(z for z in zeilen if z["year"] == 2024 and z["metric"] == "revenues")
    assert (z["report_year"], z["value"], z["conflicts"]) == (2026, 60_000_000, 2)
    assert len(strittig) == 1 and "2024" in strittig[0]


def test_proben_sind_registriert():
    assert ea.PROBE_SPALTEN in h.PROBEN and ea.PROBE_UEBERLAPPUNG in h.PROBEN


def test_store_rundlauf(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    zeilen, _ = ea.zusammenfuehren(_lies("egh_2024").kennzahlen + _lies("bbo_2024_guv").kennzahlen)
    for z in zeilen:
        z["herkunft"] = ea.herkunft_fuer(z, url="https://example.org", label="Test")
    lauf = h.Herkunft(kind="ris", url="https://example.org", label="Lauf",
                      probe=[ea.PROBE_SPALTEN], probe_result="x")
    assert store.save_enterprise_accounts(zeilen, lauf) == len(zeilen)
    rows = store.get_enterprise_accounts("egh")
    assert {r["year"] for r in rows} == {2020, 2021, 2022, 2023, 2024}
    assert store.enterprise_account_einheiten() >= {(2024, "egh"), (2024, "bbo"), (2023, "bbo")}
    assert all(r["herkunft_id"] for r in rows)
    # Ein zweiter Lauf ersetzt, verdoppelt nicht.
    store.save_enterprise_accounts(zeilen, lauf)
    assert len(store.get_enterprise_accounts()) == len(zeilen)
    store.close()


def test_pruefbericht_ohne_uebersicht_kennt_keinen_notweg():
    """Der RPA-Bericht 2022 des EGH trägt keine Mehrjahresübersicht. Der Griff
    nach der größten Zahlenzeile machte dort den Jahresüberschuss zum
    Eigenkapital — für lange Dokumente ohne GuV-/Bilanz-Label gibt es ihn nicht."""
    text = ("Jahresabschluss 2022 Eigenbetrieb Gebäudewirtschaft und Hochbau\n"
            "A.V. Jahresüberschuss/ Jahresfehlbetrag 2.103.265,69 4.360.849,65\n"
            "Summe Eigenkapital 268.241.905,50 272.602.755,15\n")
    l = ea.lies_dokument(text, FX["egh_2024"]["title"].replace("2024", "2022"),
                         "EGH Jahresabschlussbericht 2022", 1, n_pages=94)
    assert not l.kennzahlen and any("Notweg" in h for h in l.hinweise)
    # Dasselbe Dokument als kurze Anlage oder mit GuV-Label geht den Notweg.
    assert ea.lies_dokument(text, FX["egh_2024"]["title"].replace("2024", "2022"),
                            "GuV 2022", 1, n_pages=94).form == "guv+bilanz"


def test_verklebte_zeilen_gelten_nicht():
    """AWB 2025: der Textextrakt verliert die Leerzeichen — „BilanzsummeT€24.506…"
    ist keine lesbare Zeile, die Übersicht bleibt leer."""
    text = ("Die Entwicklung des Eigenbetriebs in den letzten fünf Jahren\n"
            "2025 2024 2023 2022 2021\n"
            "BilanzsummeT€24.50625.50026.49923.44022.115\n"
            "UmsatzerlöseT€24.87423.82422.04520.42620.538\n")
    l = ea.lies_dokument(text, FX["awb_2024"]["title"].replace("2024", "2025"), "Prüfbericht", 1, 96)
    assert not l.kennzahlen


def test_prozentzeile_beendet_die_tabelle():
    """Hinter der Eigenkapitalquote beginnt eine andere Tabelle — deren
    „Verbindlichkeiten" mit anderen Spalten wurden zur Kennzahl (AWB)."""
    text = (FX["awb_2024"]["text"] + "\nVerbindlichkeiten 3.600 2.700\n")
    l = ea.lies_dokument(text, FX["awb_2024"]["title"], "Anlage", 1, 90)
    verb = [k for k in l.kennzahlen if k.metric == "liabilities"]
    assert not verb
