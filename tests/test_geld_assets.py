"""Die Facette `assets` — der Anlagenspiegel.

Prüfstein: „Was ist die Stadt wert?" bekommt Buchwerte mit dem Satz, dass sie
keine Marktwerte sind; „Wie hoch ist das Eigenkapital?" bleibt bei `bilanz`."""
import pytest

from council import qa
from council.geld import assets
from council.store import CouncilStore

NAME = assets.NAME

ZIEHT = [
    "Wie hoch ist das Anlagevermögen der Stadt Oldenburg?",
    "Was sind die Straßen der Stadt wert?",
    "Wie hoch sind die Abschreibungen auf das Sachvermögen?",
    "Was besitzt die Stadt eigentlich?",
    "Wie viel ist die Stadt wert?",
]
ZIEHT_NICHT = [
    "Wie hoch ist das Eigenkapital der Stadt Oldenburg?",
    "Was plant der Eigenbetrieb im Vermögensplan?",
    "Wie hoch sind die Schulden der Stadt?",
    "Was kostet die Feuerwehr?",
]


@pytest.mark.parametrize("frage", ZIEHT)
def test_vermoegensfragen_ziehen_die_facette(frage):
    assert NAME in qa.geld_facetten(frage, "topic"), frage


@pytest.mark.parametrize("frage", ZIEHT_NICHT)
def test_bilanz_und_planfragen_ziehen_sie_nicht(frage):
    assert NAME not in qa.geld_facetten(frage, "topic"), frage


def _store(tmp_path) -> CouncilStore:
    store = CouncilStore(tmp_path / "c.sqlite")
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_provenance (id, key, kind, label, url, citation, probe, "
            "as_of, fetched_at) VALUES (1, 'k1', 'ris', 'Jahresabschluss 2024', "
            "'https://example.org/ja', '8.1 Anlagenübersicht', 'asset_row_sum', "
            "'31.12.2024', '2026-08-30')")
        for nr, label, cost, add, dep, book in (
                ("1", "Immaterielles Vermögen", 72_970_151.38, 6_067_823.62, -3_000_000.0, 55_000_000.0),
                ("2", "Sachvermögen (ohne Vorräte)", 834_357_591.39, 15_830_750.42, -30_000_000.0, 620_000_000.0),
                ("2.3", "Infrastrukturvermögen", 500_000_000.0, 9_000_000.0, -20_000_000.0, 388_206_678.0),
                ("2.2", "Bebaute Grundstücke", 200_000_000.0, 3_000_000.0, -5_000_000.0, 150_000_000.0),
                ("3", "Finanzvermögen", 120_000_000.0, 0.0, 0.0, 120_000_000.0)):
            store._conn.execute(
                "INSERT INTO council_fixed_assets (year, nr, label, n_columns, cost_opening, "
                "additions, disposals, transfers, cost_closing, depreciation_opening, depreciation, "
                "depreciation_releases, write_ups, depreciation_transfers, depreciation_closing, "
                "book_value, probes, herkunft_id, fetched_at) VALUES (2024, ?, ?, 12, ?, ?, 0, 0, "
                "?, 0, ?, 0, 0, 0, 0, ?, 'asset_row_sum', 1, '2026-08-30')",
                (nr, label, cost, add, cost, dep, book))
        store._conn.execute(
            "INSERT INTO council_vermoegensgruppen (year, group_name, book_value, "
            "book_value_prior_year, herkunft_id, fetched_at) VALUES "
            "(2024, 'Infrastrukturvermögen', 388206678.0, 387745595.32, 1, '2026-08-30')")
    return store


def test_hauptgruppen_summen_und_groesste_posten(tmp_path):
    store = _store(tmp_path)
    try:
        d = store.assets_context(["strassen"], None)
        assert d["year"] == 2024 and len(d["main"]) == 3
        assert d["total_book_value"] == 795_000_000.0
        assert d["largest"][0]["label"] == "Infrastrukturvermögen"
        b = assets.block(d)
        assert "Anlagevermögen gesamt zum 31.12.2024: 795,0 Mio. €" in b
        assert "Abschreibungen im Jahr 33,0 Mio. €" in b
        assert "Infrastrukturvermögen: Buchwert 388,2 Mio. €" in b
        assert "BUCHWERT IST KEIN MARKTWERT" in b
        assert "Beleg: Jahresabschluss 2024, 8.1 Anlagenübersicht" in b
    finally:
        store.close()


def test_fremdes_jahr_wird_angesagt(tmp_path):
    store = _store(tmp_path)
    try:
        d = store.assets_context([], 2019)
        assert d["year"] == 2024 and d["year_deviates"]
        assert "Einen Anlagenspiegel 2019 gibt es nicht" in assets.block(d)
    finally:
        store.close()
