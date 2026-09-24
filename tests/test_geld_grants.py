"""Die Facette `grants` — Zuschüsse an Dritte in der KI-Frage.

Wichtigster Wächter: Der Baustein sagt, dass es der ENTWURF ist und dass die
Beträge Ansätze sind, keine Auszahlungen.
"""
import os
from pathlib import Path

import pytest

from council import geld, qa
from council.geld import grants

ECHTE_DB = Path(os.environ.get("RATSLOTSE_MESS_DB")
                or Path(__file__).resolve().parents[1] / "data" / "council.sqlite")


@pytest.mark.parametrize("frage", [
    "Welchen Zuschuss bekommt der Reparaturrat von der Stadt?",
    "Wie hoch ist der Zuschuss für das Theater?",
    "Welche Vereine bekommen die höchsten Zuschüsse?",
    "Wird das Jugendzentrum von der Stadt bezuschusst?",
])
def test_diese_fragen_ziehen_die_zuschuesse(frage):
    assert "grants" in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", [
    "Wie viel Zuschuss gibt der Bund für Radwege?",
    "Welche Zuschüsse von der EU bekommt die Stadt?",
    "Wie viel Geld hat die Stadt 2024 an Spenden angenommen?",
    "Wie hoch sind die Schlüsselzuweisungen?",
    "Wie ist der Stand beim Stadion?",
])
def test_diese_fragen_ziehen_sie_nicht(frage):
    assert "grants" not in qa.geld_facetten(frage, "topic"), frage


def _daten(**zeilen):
    return {"year": 2026, "anderer_jahrgang": False, "anzahl": 222, "summe": 157_400_000,
            "rangfolge": False, "weitere": 0, "beleg": None,
            "zeilen": [{"description": "Zuschuss Reparaturrat", "note": None, "product_name": "Wirtschaftsförderung",
                        "sub_budget_no": 3, "amount": 61_200, "amount_prior": 61_200}], **zeilen}


def test_baustein_sagt_entwurf_und_ansatz():
    b = grants.block(_daten())
    assert "ENTWURF" in b and "ANSÄTZE" in b
    assert "Zuschuss Reparaturrat: Plan 2026 61.200 €, im Plan 2025 61.200 €" in b


def test_ohne_treffer_wird_kein_empfaenger_genannt():
    b = grants.block(_daten(zeilen=[]))
    assert "passt kein einzelner Zuschuss; nenne keinen" in b


@pytest.mark.skipif(not ECHTE_DB.exists(), reason="kein lokaler Abzug")
def test_groesse_am_echten_bestand():
    st = geld.lesestore(str(ECHTE_DB))
    try:
        for terms in (["reparaturrat"], ["theater", "staatstheater"], ["hoechsten", "vereine"]):
            b = grants.block(st.grants_context(terms))
            assert len(b) <= grants.FACETTE.grenze, (terms, len(b))
    finally:
        st.close()
