"""Gesamtfinanzhaushalt, Anlage 006 (council/finance_budget.py).

Die Fixture sind die echten Wortlisten zweier Pläne (Dok. 194222 = Plan 2019,
Dok. 297442 = Plan 2026), so wie ``pymupdf`` sie liefert, auf eine
Nachkommastelle gerundet. Zwei Pläne, weil sie zwei Nummerierungen tragen:
Bis 2022 steht die erste Summe unter 10, ab 2023 unter 09.
"""
import json
from pathlib import Path

from council import finance_budget as fb

WOERTER = json.loads((Path(__file__).parent / "fixtures" / "finanzhaushalt_woerter.json")
                     .read_text(encoding="utf-8"))


def _seiten(dok: str) -> list[list[tuple]]:
    return [[tuple(w) for w in seite] for seite in WOERTER[dok]]


def _ansatz(erg: dict, rolle: str, year: int) -> float:
    return next(z["amount"] for z in erg["zeilen"] if z["role"] == rolle and z["year"] == year)


def test_plan_2026_liest_alle_spalten_und_besteht_die_probe():
    erg = fb.lies(_seiten("297442"))
    assert erg["bestanden"], erg["nachweis"]
    assert erg["budget_year"] == 2026 and erg["years"] == list(range(2024, 2030))
    # Die hervorgehobene Planjahr-Spalte, die im Textauszug ans Zeilenende
    # wandert: Personalauszahlungen 2026 sind 202.287.524 €, nicht 214 Mio.
    personal = next(z for z in erg["zeilen"] if z["year"] == 2026 and z["label"] == "Personalauszahlungen")
    assert personal["amount"] == 202_287_524
    assert _ansatz(erg, "total_out_capital", 2026) == 69_059_840
    assert _ansatz(erg, "total_out_capital", 2029) == 41_210_240
    # Ansatz und Finanzplanung sind getrennt, Ist und Vorjahr gar nicht gespeichert.
    assert {z["kind"] for z in erg["zeilen"] if z["year"] == 2026} == {"budget"}
    assert {z["kind"] for z in erg["zeilen"] if z["year"] == 2027} == {"financial_plan"}
    assert not [z for z in erg["zeilen"] if z["year"] in (2024, 2025)]


def test_alte_nummerierung_2019_ueber_die_beschriftung():
    """Bis 2022: Posten 08 ist „Veräußerung geringwertiger
    Vermögensgegenstände", die Summe steht unter 10, und die
    Finanzmittelveränderung heißt, was ab 2023 Überschuss/Fehlbetrag heißt."""
    erg = fb.lies(_seiten("194222"))
    assert erg["bestanden"], erg["nachweis"]
    rollen = {z["role"]: z["nr"] for z in erg["zeilen"] if z["role"] and z["year"] == 2019}
    assert rollen["total_in_operating"] == 10
    assert rollen["cash_surplus"] == 33 and rollen["cash_change"] == 37
    assert round(_ansatz(erg, "total_out_capital", 2019) / 1e6, 1) == 109.8


def test_eine_verstellte_zahl_reisst_die_probe():
    seiten = _seiten("297442")
    kaputt = [[(w[0], w[1], w[2], w[3], "38.341.900" if w[4] == "38.340.900" else w[4])
               for w in seite] for seite in seiten]
    erg = fb.lies(kaputt)
    assert not erg["bestanden"] and erg["zeilen"] == []


def test_seitenzahl_und_satz_unter_der_tabelle_sind_keine_werte():
    """„Die Liquiditätsprognose zum 31.12.2025 beträgt 70 Millionen Euro" und
    die Seitenzahl im Fuß stehen rechts der Beschriftung — sie dürfen keiner
    Spalte zugeordnet werden (sonst reißt die Probe, so gemessen)."""
    _, zeilen = fb.lies_seiten(_seiten("297442"))
    werte = [v for e in zeilen.values() for v in e["werte"] if v is not None]
    assert 70.0 not in werte and 242.0 not in werte
