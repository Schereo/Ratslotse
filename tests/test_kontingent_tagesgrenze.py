"""Tagesgrenze des Recherche-Kontingents (V-07): „ab Mitternacht wieder"
stimmt nur, wenn der Tag lokal beginnt — nicht in UTC."""
from datetime import datetime, timedelta, timezone

from kern.store import Store, _tagesbeginn_utc

# --- Tagesgrenze des Recherche-Kontingents (V-07) ---


def test_tagesgrenze_folgt_oldenburger_mitternacht():
    """Die Oberfläche sagt „ab Mitternacht wieder" — das galt nicht, solange
    per UTC-Datum gezählt wurde (im Sommer erst ab 2 Uhr nachts). Der
    Tagesbeginn liegt jetzt bei der LOKALEN Mitternacht, ausgedrückt als
    UTC-Zeitstempel (so liegt `created` in der Tabelle)."""
    beginn = datetime.fromisoformat(_tagesbeginn_utc())
    jetzt = datetime.utcnow()
    assert beginn <= jetzt                       # nie in der Zukunft
    assert jetzt - beginn < timedelta(hours=25)  # und höchstens einen Tag her
    try:
        from zoneinfo import ZoneInfo
    except ImportError:  # pragma: no cover
        return
    lokal = beginn.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Europe/Berlin"))
    assert (lokal.hour, lokal.minute, lokal.second) == (0, 0, 0)


def test_kontingent_zaehlt_nur_ab_lokaler_mitternacht(tmp_path):
    store = Store(tmp_path / "nwz.sqlite")
    try:
        vor = (datetime.fromisoformat(_tagesbeginn_utc()) - timedelta(minutes=5)) \
            .isoformat(timespec="seconds")
        nach = (datetime.fromisoformat(_tagesbeginn_utc()) + timedelta(minutes=5)) \
            .isoformat(timespec="seconds")
        with store._conn:
            store._conn.executemany(
                "INSERT INTO deep_research_jobs (id, user_id, frage, status, created, updated) "
                "VALUES (?, 7, 'x', 'fertig', ?, ?)",
                [("alt", vor, vor), ("neu", nach, nach)])
        assert store.deep_jobs_heute(7) == 1     # nur der Job von heute zählt
    finally:
        store.close()
