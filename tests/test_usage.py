"""LLM-Kosten-Dashboard (Admin 21a): Verlauf, Monat, Hochrechnung, Budget-Ampel."""
from __future__ import annotations

import calendar
from datetime import date, timedelta

import pytest

from nwz import usage


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
