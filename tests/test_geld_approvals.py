"""Die Facette `approvals` — die einzelnen Nachbewilligungen.

Prüfstein: „Wofür wurde bewilligt?" bekommt die Posten mit Titel und Betrag;
die Summe je Jahr liefert die alte `supplementary_approvals` daneben."""
import pytest

from council import qa
from council.geld import approvals
from council.store import CouncilStore

NAME = approvals.NAME

ZIEHT = [
    "Wofür hat die Stadt 2024 außerplanmäßig Geld bewilligt?",
    "Welche Nachbewilligungen gab es für die Klävemann-Stiftung?",
    "Was wurde 2024 nachbewilligt?",
    "Welche überplanmäßigen Bewilligungen gab es?",
]
ZIEHT_NICHT = [
    "Wie hoch sind die Schulden der Stadt?",
    "Was kostet die Feuerwehr?",
    "Welche Fördermittel hat die Stadt bekommen?",
    "Wie hoch ist der Hebesatz für die Grundsteuer B?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_bewilligungsfragen_ziehen_die_facette(frage):
    assert NAME in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_andere_fragen_ziehen_sie_nicht(frage):
    assert NAME not in qa.geld_facetten(frage, "topic"), frage


def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, probe, "
            "as_of, fetched_at) VALUES (1, 'k1', 'ris', 'Vorlagen im RIS', "
            "'https://example.org/v', 'Titel und Beschlussvorschlag', 'title_amount', "
            "'2024', '2026-08-30')")
        for nr, year, title, kind, cat, amount, decided in (
                ("24/0100", 2024, "Überplanmäßige Bewilligung in Höhe von 11.200.000 Euro für Sozialleistungen - Beschluss -", "approval", "excess", 11_200_000.0, 1),
                ("24/0200", 2024, "Außerplanmäßige Bewilligung in Höhe von 500.000 Euro für die Klävemann-Stiftung - Beschluss -", "approval", "unbudgeted", 500_000.0, 1),
                ("24/0300", 2024, "Verpflichtungsermächtigung 3.000.000 Euro Schulbau - Beschluss", "commitment_authorization", "excess", 3_000_000.0, 0),
                ("23/0900", 2023, "Überplanmäßige Bewilligung 800.000 Euro Feuerwehr - Beschluss", "approval", "excess", 800_000.0, 1)):
            store._conn.execute(
                "INSERT INTO council_supplementary_approvals (template_number, year, title, kind, "
                "category, amount, amount_source, decided, in_plenary, council_decision, "
                "fulltext_probe, herkunft_id, fetched_at) VALUES (?,?,?,?,?,?,'title',?,1,1,1,1,"
                "'2026-08-30')", (nr, year, title, kind, cat, amount, decided))
    return store


def test_posten_groesste_zuerst_summe_ohne_ve(tmp_path):
    store = _store(tmp_path)
    try:
        d = store.approvals_context(["stadt", "geld"], 2024)
        assert d["count"] == 3 and d["sum_approvals"] == 11_700_000.0
        assert d["items"][0]["template_number"] == "24/0100"
        b = approvals.block(d)
        assert "3 Vorlagen im Jahr 2024, Bewilligungen mit Betrag zusammen 11,7 Mio. €" in b
        assert "11,2 Mio. € — Überplanmäßige Bewilligung in Höhe von 11.200.000 Euro für Sozialleistungen (Vorlage 24/0100; überplanmäßig Bewilligung, vom Rat beschlossen)" in b
        assert "Verpflichtungsermächtigung, Beschluss nicht bestätigt" in b
    finally:
        store.close()


def test_suchbegriffe_ziehen_den_passenden_posten_nach_vorn(tmp_path):
    store = _store(tmp_path)
    try:
        d = store.approvals_context(["klaevemann", "stiftung"], 2024)
        assert d["matched"] == 1 and d["items"][0]["template_number"] == "24/0200"
        assert "1 passen zu den Suchbegriffen" in approvals.block(d)
    finally:
        store.close()


def test_fremdes_jahr_wird_angesagt(tmp_path):
    store = _store(tmp_path)
    try:
        d = store.approvals_context([], 2019)
        assert d["year"] == 2024 and d["year_deviates"]
        assert "Für 2019 gibt es keine Nachbewilligungs-Vorlagen" in approvals.block(d)
    finally:
        store.close()
