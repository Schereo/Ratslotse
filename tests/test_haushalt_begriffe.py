"""Der Geld-Kontext muss deutsche Komposita treffen."""
import pytest
from council.store import CouncilStore


@pytest.fixture()
def store(tmp_path):
    s = CouncilStore(str(tmp_path / "c.sqlite"))
    for area, aufw, summe in (
            ("Verkehr und Straßenbau", 43.8e6, 0),
            ("Kultur, Museen, Sport", 35.8e6, 0),
            ("Klima/Umwelt/Mobilität/Bau/Grün/Friedh.", 31.5e6, 0),
            ("Stadtplanung", 7.5e6, 0),
            ("Summe", 817.3e6, 1)):
        s._conn.execute(
            "INSERT INTO council_haushalt (year, area, revenues, expenses,"
            " result, is_total, source_url, fetched_at) "
            "VALUES (2025, ?, 0, ?, 0, ?, '', '2026-08-20')", (area, aufw, summe))
    s._conn.commit()
    return s


def _bereiche(store, begriffe):
    return [r["area"] for r in store.haushalt_fuer_begriffe(begriffe)]


def test_blosses_bereichswort_trifft_weiterhin(store):
    assert "Verkehr und Straßenbau" in _bereiche(store, ["Verkehr"])


@pytest.mark.parametrize("begriff, area", [
    ("Radverkehr", "Verkehr und Straßenbau"),        # Grundwort am ENDE
    ("Mobilitätsplan", "Klima/Umwelt/Mobilität/Bau/Grün/Friedh."),  # am ANFANG
    ("Kongresshalle", "Kultur, Museen, Sport"),      # nur übers Synonym
    ("Baumschutzsatzung", "Klima/Umwelt/Mobilität/Bau/Grün/Friedh."),
    ("Sanierungsgebiet", "Stadtplanung"),
])
def test_komposita_finden_ihren_teilhaushalt(store, begriff, area):
    """Alle fünf lieferten am 20.08.2026 auf Prod null Zeilen."""
    assert area in _bereiche(store, [begriff])


def test_transport_holt_nicht_den_sport(store):
    """„sport" steckt in „Transport“ — aber nicht am Wortrand."""
    assert "Kultur, Museen, Sport" not in _bereiche(store, ["Transportkosten"])


def test_gesamthaushalt_liefert_die_summenzeile(store):
    assert _bereiche(store, ["Haushalt"]) == ["Summe"]


def test_ohne_bezug_keine_zeile(store):
    assert _bereiche(store, ["Ausfallbürgschaft", "Notifizierung"]) == []
