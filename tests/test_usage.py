"""LLM-Kosten-Dashboard (Admin 21a): Verlauf, Monat, Hochrechnung, Budget-Ampel."""
from __future__ import annotations

import calendar
from datetime import date, timedelta

import pytest

from kern import usage


@pytest.fixture
def usage_db(tmp_path, monkeypatch):
    db = tmp_path / "nwz.sqlite"
    monkeypatch.setenv("NWZ_SQLITE", str(db))
    return db


def _insert(db, ts: str, feature: str, model: str, pin: int, pout: int):
    import sqlite3
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS llm_usage (id INTEGER PRIMARY KEY, ts TEXT NOT NULL "
        "DEFAULT (datetime('now')), feature TEXT NOT NULL, model TEXT, "
        "prompt_tokens INTEGER, completion_tokens INTEGER)")
    conn.execute("INSERT INTO llm_usage(ts, feature, model, prompt_tokens, completion_tokens) "
                 "VALUES (?,?,?,?,?)", (ts, feature, model, pin, pout))
    conn.commit()
    conn.close()


def test_cost_timeseries_is_gap_filled_and_ordered(usage_db):
    today = date.today()
    # Zwei Tage mit Nutzung, dazwischen eine Lücke.
    _insert(usage_db, f"{today - timedelta(days=2)} 10:00:00", "qa_antwort", "openai/gpt-4o", 1_000_000, 0)
    _insert(usage_db, f"{today} 09:00:00", "qa_antwort", "openai/gpt-4o", 0, 1_000_000)
    series = usage.cost_timeseries(days=3)
    assert [d["date"] for d in series] == [
        (today - timedelta(days=2)).isoformat(),
        (today - timedelta(days=1)).isoformat(),
        today.isoformat(),
    ]
    assert series[0]["cost"] == pytest.approx(2.5)   # 1M input × $2.50
    assert series[1]["cost"] == 0.0 and series[1]["calls"] == 0  # Lücke aufgefüllt
    assert series[2]["cost"] == pytest.approx(10.0)  # 1M output × $10.00


def test_dashboard_projection_and_budget_levels(usage_db):
    today = date.today()
    # Eine Zeile heute → Monatskosten = heutige Kosten.
    _insert(usage_db, f"{today} 08:00:00", "protokoll_extraktion", "openai/gpt-4o", 4_000_000, 0)  # $10
    d = usage.dashboard(budget_monthly=40.0)
    assert d["cost_month"] == pytest.approx(10.0)
    # Hochrechnung: 10 / heutiger-Tag × Monatstage.
    month_days = calendar.monthrange(today.year, today.month)[1]
    assert d["projected_month"] == pytest.approx(round(10.0 / today.day * month_days, 2))
    assert d["budget_pct"] == round(100 * 10.0 / 40.0)
    assert d["budget_level"] == ("ok" if d["budget_pct"] < 80 else "warn" if d["budget_pct"] < 100 else "over")
    # Feature-Aggregat bleibt erhalten.
    assert d["features"] and d["features"][0]["feature"] == "protokoll_extraktion"


def test_budget_ampel_thresholds(usage_db):
    today = date.today()
    _insert(usage_db, f"{today} 08:00:00", "qa_antwort", "openai/gpt-4o", 4_000_000, 0)  # $10
    assert usage.dashboard(budget_monthly=100.0)["budget_level"] == "ok"    # 10 %
    assert usage.dashboard(budget_monthly=12.0)["budget_level"] == "warn"   # 83 %
    assert usage.dashboard(budget_monthly=8.0)["budget_level"] == "over"    # 125 %


# ---- Echte OpenRouter-Kosten (cost_usd) vs. PRICES-Schätzung ----------------

def test_summary_bevorzugt_echte_kosten(usage_db):
    # Eine Zeile MIT echtem Kostenwert (weit unter der Schätzung) und eine
    # Alt-Zeile ohne — die Summe muss echt + geschätzt mischen.
    usage.record("qa_antwort", "openai/gpt-4o", 1_000_000, 0, cost_usd=0.5)
    usage.record("qa_antwort", "openai/gpt-4o", 1_000_000, 0)  # ohne → Schätzung 2.5
    s = usage.summary()
    f = next(x for x in s["features"] if x["feature"] == "qa_antwort")
    assert f["cost"] == pytest.approx(3.0)


def test_timeseries_bevorzugt_echte_kosten(usage_db):
    from datetime import date
    usage.record("qa_antwort", "openai/gpt-4o", 1_000_000, 0, cost_usd=0.25)
    heute = next(d for d in usage.cost_timeseries(days=1) if d["date"] == date.today().isoformat())
    assert heute["cost"] == pytest.approx(0.25)


def test_record_ohne_cost_bleibt_kompatibel(usage_db):
    usage.record("qa_antwort", "unbekanntes/modell", 100, 100)  # kein Preis, kein cost
    s = usage.summary()
    assert s["total_calls"] == 1 and s["total_cost"] == 0.0


def test_llm_session_cost_zaehler(monkeypatch):
    from types import SimpleNamespace
    from kern import llm
    monkeypatch.setattr(llm, "_session_cost", {"usd": 0.0, "calls_mit": 0, "calls_ohne": 0})
    monkeypatch.setattr("kern.usage.record", lambda *a, **k: None)
    llm._record_usage("qa_antwort", "m", SimpleNamespace(prompt_tokens=1, completion_tokens=1, cost=0.0012))
    llm._record_usage("qa_antwort", "m", SimpleNamespace(prompt_tokens=1, completion_tokens=1))
    sc = llm.session_cost()
    assert sc["usd"] == pytest.approx(0.0012)
    assert sc["calls_mit"] == 1 and sc["calls_ohne"] == 1


def test_zeitstempel_werden_als_lokale_tage_gezaehlt(usage_db):
    """Ein UTC-Zeitstempel, der lokal auf einen anderen Tag fällt, wird dem
    LOKALEN Tag zugeordnet.

    ``llm_usage.ts`` kommt aus SQLites ``datetime('now')`` und ist UTC;
    ``cost_timeseries`` vergleicht gegen ``date.today()``, also den lokalen
    Tag. Ohne Umrechnung fiel die Kostenübersicht in Deutschland jede Nacht
    zwischen 0 und 2 Uhr auf null zurück — sie suchte einen Tag, den es in den
    Daten noch nicht gab.

    Der bestehende Test dazu deckt es nur auf, wenn er zufällig in diesem
    Zeitfenster läuft (so am 17.08.2026 um 00:45). Dieser hier prüft es zu
    jeder Tageszeit, indem er den Grenzfall selbst herstellt: ein Eintrag um
    23:30 UTC, der in jeder Zeitzone östlich von Greenwich schon zum Folgetag
    gehört.
    """
    import sqlite3
    from datetime import datetime, timedelta, timezone

    usage.record("qa_antwort", "openai/gpt-4o", 1000, 0, cost_usd=0.5)

    # Den eben geschriebenen Eintrag auf 23:30 UTC von vorgestern setzen.
    utc_ts = (datetime.now(timezone.utc) - timedelta(days=2)).replace(
        hour=23, minute=30, second=0, microsecond=0)
    conn = sqlite3.connect(usage_db)
    conn.execute("UPDATE llm_usage SET ts = ?", (utc_ts.strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()
    conn.close()

    # Derselbe Zeitpunkt, in lokaler Zeit gelesen — das ist der Tag, unter dem
    # er erscheinen muss.
    erwartet = utc_ts.astimezone().date().isoformat()
    reihe = {d["date"]: d["cost"] for d in usage.cost_timeseries(days=5)}
    assert reihe.get(erwartet) == pytest.approx(0.5), (
        f"Eintrag von {utc_ts:%Y-%m-%d %H:%M} UTC gehört zum lokalen Tag "
        f"{erwartet}, steht aber nicht dort: {reihe}")
