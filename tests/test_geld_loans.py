"""Die Facette `loans` — zu welchem Zins die Stadt sich Geld leiht."""
import pytest

from council import herkunft as h, loans as parser, qa
from council.geld import loans
from council.store import CouncilStore

NAME = loans.NAME

ZIEHT = [
    "Zu welchem Zinssatz hat die Stadt zuletzt einen Kredit aufgenommen?",
    "Wie hoch sind die Zinsen für die Kredite der Stadt?",
    "Hat Oldenburg 2025 Kredite umgeschuldet?",
    "Was zahlt der Bäderbetrieb für sein Darlehen?",
    "Wie lange ist die Zinsbindung der städtischen Kredite?",
]
ZIEHT_NICHT = [
    "Wie ist der Stand beim Stadion?",
    "Was hat der Rat zur Baumschutzsatzung beschlossen?",
    "Wer ist Oberbürgermeister von Oldenburg?",
    "Was kostet die Feuerwehr?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_zieht(frage):
    assert NAME in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_zieht_nicht(frage):
    assert NAME not in qa.geld_facetten(frage, "topic"), frage


def test_schulden_und_kredite_kommen_zusammen():
    f = qa.geld_facetten("Wie hoch sind die Schulden und was zahlt die Stadt an Zinsen?", "money")
    assert {"schulden", NAME} <= f


def _store(tmp_path) -> CouncilStore:
    st = CouncilStore(tmp_path / "c.sqlite")
    lauf = h.Herkunft(kind="ris", url="https://example.org", label="Lauf", probe=[parser.ZEITRAUM], probe_result="x")
    notices = [
        {"template_number": "25/0527", "year": 2025, "period_from": "2025-06", "period_to": "2025-08",
         "document_date": "2025-08-19", "none_reported": 0, "items": 2, "probes": [parser.ZEITRAUM, parser.POSTEN_BETRAG],
         "herkunft": h.Herkunft(kind="ris", url="https://example.org/25-0527", label="Unterrichtung — Vorlage 25/0527",
                                citation=parser.FUNDSTELLE, probe=[parser.ZEITRAUM], probe_result="ok")},
        {"template_number": "22/0056", "year": 2022, "period_from": "2022-01", "period_to": "2022-02",
         "document_date": "2022-02-15", "none_reported": 0, "items": 1, "interest_saving": 75604.35,
         "saving_from": "2021-11-16", "saving_to": "2022-02-16", "probes": [parser.ZEITRAUM]},
    ]
    items = [
        {"template_number": "25/0527", "seq": 1, "year": 2025, "kind": "loan", "borrower": "Bäderbetrieb Oldenburg",
         "heading": "Kreditaufnahme des Bäderbetriebs Oldenburg am Kapitalmarkt in Höhe von 9.742.709,00 Euro",
         "amount": 9_742_709.0, "rate_pct": 3.03, "decided_at": "2025-06-05", "summary": "…"},
        {"template_number": "25/0527", "seq": 2, "year": 2025, "kind": "refinancing", "borrower": None,
         "heading": "Umschuldung von Kommunalkrediten (Grundgeschäfte) in Höhe von insgesamt 52.427.952,02 Euro",
         "amount": 52_427_952.02, "summary": "…"},
        {"template_number": "22/0056", "seq": 1, "year": 2022, "kind": "refinancing", "borrower": None,
         "heading": "Umschuldung von Kommunalkrediten in Höhe von insgesamt 78.812.404,40 Euro",
         "amount": 78_812_404.40, "summary": "…"},
    ]
    st.save_loan_notices(notices, items, lauf)
    return st


def test_baustein_nennt_zins_umschuldung_und_ersparnis(tmp_path):
    st = _store(tmp_path)
    d = st.loans_context([], None)
    assert d["year"] == 2025
    assert d["rates"][0]["rate_pct"] == pytest.approx(3.03)
    assert d["latest_refinancing"]["amount"] == pytest.approx(52_427_952.02)
    assert d["saving"]["interest_saving"] == pytest.approx(75604.35)
    text = loans.block(d)
    assert "Zinssatz 3,03 %" in text and "Bäderbetrieb Oldenburg" in text
    assert "Zuletzt umgeschuldet (2025-06 bis 2025-08): 52,4 Mio. € Kommunalkredite" in text
    assert "NIE addieren" in text
    assert "75.604 €" in text and "keine Rechnung von uns" in text
    assert "Beleg: Unterrichtung — Vorlage 25/0527" in text
    assert "NICHT bekannt" in text
    st.close()


def test_begriffe_und_jahr(tmp_path):
    st = _store(tmp_path)
    d = st.loans_context(["Bäderbetrieb"], 2022)
    assert d["year"] == 2022 and "year_asked" not in d
    assert d["positions"][0]["borrower"] == "Bäderbetrieb Oldenburg"
    d = st.loans_context([], 2019)
    assert d["year"] == 2025 and d["year_asked"] == 2019
    assert "Für 2019 liegt keine Unterrichtung vor" in loans.block(d)
    st.close()
