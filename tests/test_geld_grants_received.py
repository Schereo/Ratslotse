"""Die Facette `grants_received` — Fördermittel von EU und Bund in der KI-Frage.

Wichtigster Wächter: Der Baustein sagt, dass Städtebauförderung und
Landesprogramme fehlen — aus einer fehlenden Zeile folgt keine fehlende
Förderung.
"""
import os
from pathlib import Path

import pytest

from council import geld, qa
from council.geld import grants_received

ECHTE_DB = Path(os.environ.get("RATSLOTSE_MESS_DB")
                or Path(__file__).resolve().parents[1] / "data" / "council.sqlite")


@pytest.mark.parametrize("frage", [
    "Welche Fördermittel bekommt die Stadt von der EU?",
    "Hat die VWG Förderung vom Bund für Wasserstoffbusse bekommen?",
    "Wie viel Zuschuss gibt der Bund für Radwege?",
    "Welche EFRE-Projekte gibt es in Oldenburg?",
])
def test_diese_fragen_ziehen_die_foerdermittel(frage):
    assert "grants_received" in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", [
    "Welchen Zuschuss bekommt der Reparaturrat von der Stadt?",
    "Wie hoch sind die Schlüsselzuweisungen?",
    "Wie viel Geld hat die Stadt 2024 an Spenden angenommen?",
    "Wie ist der Stand beim Stadion?",
])
def test_diese_fragen_ziehen_sie_nicht(frage):
    assert "grants_received" not in qa.geld_facetten(frage, "topic"), frage


def test_baustein_nennt_die_grenzen():
    b = grants_received.block({
        "summen": {"EU": [50, 8_268_033], "Bund": [51, 15_468_451]}, "treffer": True, "year": None,
        "weitere": 0, "stand": "2026-01-31", "beleg": None,
        "zeilen": [{"title": "Anschaffung von vier Kraftomnibussen mit Wasserstoffantrieb",
                    "recipient": "Verkehr und Wasser GmbH", "funder": "EU", "program": "EFRE 2014-2020",
                    "amount_granted": 1_212_218, "start": "2021-02-01", "end": "2023-03-31"}]})
    assert "BEWILLIGUNGEN, keine Auszahlungen" in b
    assert "Städtebauförderung" in b and "folgt daraus NICHT" in b
    assert "Laufzeit 2021–2023: bewilligt 1,2 Mio. €" in b


@pytest.mark.skipif(not ECHTE_DB.exists(), reason="kein lokaler Abzug")
def test_groesse_und_treffer_am_echten_bestand():
    st = geld.lesestore(str(ECHTE_DB))
    try:
        d = st.grants_received_context(["wasserstoff", "busse"])
        if d is None:
            pytest.skip("keine Fördermittel im Abzug")
        assert any("Wasserstoff" in z["title"] for z in d["zeilen"])
        for terms in (["wasserstoff"], [], ["radwege"]):
            b = grants_received.block(st.grants_received_context(terms))
            assert len(b) <= grants_received.FACETTE.grenze, (terms, len(b))
    finally:
        st.close()
