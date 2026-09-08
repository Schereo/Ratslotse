"""Wie viel Post ein Ausschuss-Abo kostet (Teil B / PR 9).

Der Anlass: Am 08.09.2026 hatten vier Konten binnen fünfzehn Sekunden ALLE
sechzehn Ausschüsse abonniert — ein Klick, kein Abwägen. Zwei davon bekamen
daraufhin rund zwanzig Tagesordnungs-Mails und waren nie wieder da. Die Zahl
stand nirgends, bevor man sie bekam.
"""
from __future__ import annotations

from datetime import date, timedelta

from council.store import CouncilStore


def _sitzung(store, ksinr: int, committee: str, tage_her: int) -> None:
    tag = (date.today() - timedelta(days=tage_her)).isoformat()
    with store._conn:
        store._conn.execute(
            "INSERT INTO council_sessions (ksinr, committee, session_date, session_time,"
            " location, fetched_at) VALUES (?, ?, ?, '17:00', 'Rathaus', ?)",
            (ksinr, committee, tag, tag))


def test_zaehlt_je_gremium(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    for i in range(3):
        _sitzung(store, 100 + i, "Rat", 30 * (i + 1))
    _sitzung(store, 200, "Verkehrsausschuss", 40)

    zahlen = store.sitzungszahl_je_gremium((date.today() - timedelta(days=365)).isoformat())

    assert zahlen == {"Rat": 3, "Verkehrsausschuss": 1}
    store.close()


def test_alte_sitzungen_fallen_aus_dem_fenster(tmp_path):
    store = CouncilStore(tmp_path / "c.sqlite")
    _sitzung(store, 1, "Rat", 30)
    _sitzung(store, 2, "Rat", 800)
    zahlen = store.sitzungszahl_je_gremium((date.today() - timedelta(days=365)).isoformat())
    assert zahlen["Rat"] == 1
    store.close()


def test_geplante_sitzungen_zaehlen_nicht_mit(tmp_path):
    """Gezählt wird, was stattgefunden hat — das ist die ehrlichere Vorhersage."""
    store = CouncilStore(tmp_path / "c.sqlite")
    _sitzung(store, 1, "Rat", 30)
    _sitzung(store, 2, "Rat", -40)  # in der Zukunft
    zahlen = store.sitzungszahl_je_gremium((date.today() - timedelta(days=365)).isoformat())
    assert zahlen["Rat"] == 1
    store.close()


def test_gremien_ohne_sitzung_fehlen(tmp_path):
    """Der Aufrufer setzt 0 — eine Zeile je Gremium wäre eine zweite Liste."""
    store = CouncilStore(tmp_path / "c.sqlite")
    assert store.sitzungszahl_je_gremium("2020-01-01") == {}
    store.close()
