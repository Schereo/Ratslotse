"""Die Facette `liquidity` — der Kontostand am Monatsende."""
import pytest

from council import herkunft as h, liquidity as parser, qa
from council.geld import liquidity
from council.store import CouncilStore

NAME = liquidity.NAME


@pytest.mark.parametrize("frage", [
    "Wie viel Geld hat die Stadt Oldenburg gerade auf dem Konto?",
    "Wie steht es um die Liquidität der Stadt?",
    "Ist Oldenburg noch zahlungsfähig?",
    "Wie hoch war der Kassenstand Ende 2024?",
])
def test_zieht(frage):
    assert NAME in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", [
    "Wie ist der Stand beim Stadion?",
    "Was hat der Rat zur Baumschutzsatzung beschlossen?",
    "Was kostet die Feuerwehr?",
    "Wie hoch sind die Schulden der Stadt?",
])
def test_zieht_nicht(frage):
    assert NAME not in qa.geld_facetten(frage, "topic"), frage


def _store(tmp_path) -> CouncilStore:
    st = CouncilStore(tmp_path / "c.sqlite")
    lauf = h.Herkunft(kind="ris", url="https://example.org", label="Lauf", probe=[parser.WERTZAHL], probe_result="x")
    rows = []
    werte = {"2024-12": 116.0, "2025-01": 105.0, "2025-06": 114.7, "2025-12": 108.0, "2026-01": 84.8, "2026-05": 136.1}
    for m, v in werte.items():
        rows.append({"month": m, "year": int(m[:4]), "amount": v * 1e6, "as_of": "2026-05-31",
                     "confirmations": 2, "probes": [parser.WERTZAHL, parser.UEBERLAPPUNG],
                     "template_number": "26/0483", "url": "https://example.org/g",
                     "herkunft": h.Herkunft(kind="ris", url="https://example.org/g", label="Grafik 26/0483",
                                            citation=parser.FUNDSTELLE, probe=[parser.WERTZAHL], probe_result="ok")})
    rows.append({"month": "2016-07", "year": 2016, "amount": -7.6e6, "as_of": "2016-07-31", "confirmations": 4,
                 "probes": [parser.WERTZAHL], "template_number": "16/0400", "url": "https://example.org/h"})
    st.save_liquidity(rows, lauf)
    return st


def test_baustein_nennt_stand_spanne_und_tiefpunkt(tmp_path):
    st = _store(tmp_path)
    d = st.liquidity_context([], None)
    assert d["latest"]["month"] == "2026-05" and d["lowest"]["amount"] == pytest.approx(-7.6e6)
    text = liquidity.block(d)
    assert "Kontostand Ende Mai 2026: 136,1 Mio. €" in text
    assert "Ende Dezember: 2024: 116,0 Mio. €, 2025: 108,0 Mio. €" in text
    assert "Ende Juli 2016 — unter null" in text
    assert "Beleg: Grafik 26/0483" in text and "KONTOSTAND" in text
    st.close()


def test_gefragtes_jahr_und_rueckfall(tmp_path):
    st = _store(tmp_path)
    d = st.liquidity_context([], 2025)
    assert d["year"] == 2025 and [r["month"] for r in d["asked_year_rows"]] == ["2025-01", "2025-06", "2025-12"]
    assert "Ende Juni 2025: 114,7 Mio. €" in liquidity.block(d)
    d = st.liquidity_context([], 2019)
    assert d["year_asked"] == 2019 and "Für 2019 liegt keine Grafik vor" in liquidity.block(d)
    st.close()
