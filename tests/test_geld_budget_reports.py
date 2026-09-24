"""Die Facette `budget_reports` — Budgetberichte in der KI-Frage.

Wichtigster Wächter: Angedockt an Investitionsfragen liefert sie nur, wenn
eine Maßnahme getroffen wird — sonst wüchse jeder Investitions-Prompt.
"""
import os
from pathlib import Path

import pytest

from council import geld, qa
from council.geld import budget_reports

ECHTE_DB = Path(os.environ.get("RATSLOTSE_MESS_DB")
                or Path(__file__).resolve().parents[1] / "data" / "council.sqlite")


@pytest.mark.parametrize("frage", [
    "Wird die Kita Dedestraße dieses Jahr fertig, laut Prognose im Budgetbericht?",
    "Was steht im Budgetbericht des Jugendhilfeausschusses?",
    "Warum fließen die Mittel für die Kitas nicht ab?",
    "Was wird aus den Kita-Investitionen dieses Jahr?",
])
def test_diese_fragen_ziehen_die_budgetberichte(frage):
    assert "budget_reports" in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", [
    "Was kostet der Ausbau der Nadorster Straße?",
    "Wie hoch sind die Schulden der Stadt?",
    "Wie ist der Stand beim Stadion?",
])
def test_diese_fragen_ziehen_sie_nicht(frage):
    assert "budget_reports" not in qa.geld_facetten(frage, "topic"), frage


def test_baustein_erklaert_prognose_ueber_ansatz():
    b = budget_reports.block({
        "summen": [{"sub_budget_no": 11, "as_of": "2026-06-30", "budget_year": 2026,
                    "planned": 1_519_000, "forecast": 2_320_000}], "weitere": 0, "beleg": None,
        "zeilen": [{"name": "Inv.Zuschuss Kita Dedestraße", "measure_no": "I10.170066.525.008",
                    "kind": "A", "as_of": "2026-06-30", "budget_year": 2026, "planned": 0,
                    "forecast": 163_059, "note": "Der Erweiterungsbau der Krippe wurde fertiggestellt."}]})
    assert "Ermächtigungsübertragung" in b and "keine Überschreitung" in b
    assert "Bericht zum 30.06.2026: Ansatz 2026 0 €, Prognose Jahresende 2026 163.059 €" in b
    assert "„Der Erweiterungsbau der Krippe wurde fertiggestellt.“" in b


@pytest.mark.skipif(not ECHTE_DB.exists(), reason="kein lokaler Abzug")
def test_ohne_treffer_bleibt_der_prompt_kurz_und_groesse():
    st = geld.lesestore(str(ECHTE_DB))
    try:
        if st.budget_reports_context(["prognose"]) is None:
            pytest.skip("keine Budgetberichte im Abzug")
        assert st.budget_reports_context(["stadion", "marschweg"]) is None
        d = st.budget_reports_context(["kita", "dedestrasse"])
        assert "Dedestraße" in d["zeilen"][0]["name"]
        for terms in (["kita", "dedestrasse"], ["prognose"], ["schule", "digitalpakt"]):
            b = budget_reports.block(st.budget_reports_context(terms))
            assert len(b) <= budget_reports.FACETTE.grenze, (terms, len(b))
    finally:
        st.close()
