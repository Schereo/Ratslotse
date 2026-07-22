"""Lightweight LLM-usage tracking, so the admin page can show where the model spend
goes (tokens + estimated cost per feature).

Best-effort by design: recording must NEVER break an LLM call, and under write
contention (parallel backfills) a dropped row just means slightly under-counted stats.
Rows land in ``llm_usage`` in the shared nwz.sqlite.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "nwz.sqlite"

# $ per 1M tokens (input, output). Extend when a new model is used.
PRICES: dict[str, tuple[float, float]] = {
    "deepseek/deepseek-v4-pro": (0.435, 0.87),
    "deepseek/deepseek-v4-flash": (0.10, 0.20),
    "openai/gpt-4o": (2.5, 10.0),
    "openai/gpt-4o-mini": (0.15, 0.60),
}


def _db() -> str:
    return os.environ.get("NWZ_SQLITE") or str(_DEFAULT_DB)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db(), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS llm_usage ("
        "id INTEGER PRIMARY KEY, ts TEXT NOT NULL DEFAULT (datetime('now')), "
        "feature TEXT NOT NULL, model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER)")
    return conn


def record(feature: str, model: str | None, prompt_tokens: int, completion_tokens: int) -> None:
    """Append one usage row. Swallows all errors — tracking is never load-bearing."""
    try:
        conn = _connect()
        with conn:
            conn.execute(
                "INSERT INTO llm_usage(feature, model, prompt_tokens, completion_tokens) VALUES (?,?,?,?)",
                (feature, model, int(prompt_tokens or 0), int(completion_tokens or 0)))
        conn.close()
    except Exception:  # noqa: BLE001 — usage tracking must never break an LLM call
        pass


def _cost(model: str | None, pin: int, pout: int) -> float:
    p = PRICES.get(model or "", (0.0, 0.0))
    return pin / 1e6 * p[0] + pout / 1e6 * p[1]


def summary() -> dict:
    """Per-feature aggregate (calls, tokens, estimated $, models, span) + totals,
    most expensive first. Empty if nothing has been recorded yet."""
    try:
        conn = _connect()
        rows = conn.execute(
            "SELECT feature, model, COUNT(*) calls, COALESCE(SUM(prompt_tokens),0) pin, "
            "COALESCE(SUM(completion_tokens),0) pout, MIN(ts) first, MAX(ts) last "
            "FROM llm_usage GROUP BY feature, model").fetchall()
        conn.close()
    except Exception:  # noqa: BLE001
        return {"features": [], "total_cost": 0.0, "total_calls": 0}

    feats: dict = {}
    for r in rows:
        f = feats.setdefault(r["feature"], {
            "feature": r["feature"], "calls": 0, "prompt_tokens": 0, "completion_tokens": 0,
            "cost": 0.0, "models": set(), "first": r["first"], "last": r["last"]})
        f["calls"] += r["calls"]
        f["prompt_tokens"] += r["pin"]
        f["completion_tokens"] += r["pout"]
        f["cost"] += _cost(r["model"], r["pin"], r["pout"])
        if r["model"]:
            f["models"].add(r["model"])
        f["first"] = min(f["first"], r["first"])
        f["last"] = max(f["last"], r["last"])
    out = []
    for f in feats.values():
        f["models"] = sorted(f["models"])
        f["cost"] = round(f["cost"], 4)
        out.append(f)
    out.sort(key=lambda x: -x["cost"])
    return {"features": out, "total_cost": round(sum(f["cost"] for f in out), 4),
            "total_calls": sum(f["calls"] for f in out)}


def cost_timeseries(days: int = 30) -> list[dict]:
    """Tägliche geschätzte Kosten + Aufrufe der letzten ``days`` Tage — lückenlos
    (fehlende Tage = 0), ältester zuerst. Kosten werden aus Tokens × Modellpreis
    je Zeile summiert (cost steht nicht in der DB)."""
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    try:
        conn = _connect()
        rows = conn.execute(
            "SELECT date(ts) d, model, COUNT(*) calls, "
            "COALESCE(SUM(prompt_tokens),0) pin, COALESCE(SUM(completion_tokens),0) pout "
            "FROM llm_usage WHERE date(ts) >= ? GROUP BY date(ts), model",
            (since,)).fetchall()
        conn.close()
    except Exception:  # noqa: BLE001
        return []
    by_day: dict[str, dict] = {}
    for r in rows:
        e = by_day.setdefault(r["d"], {"cost": 0.0, "calls": 0})
        e["cost"] += _cost(r["model"], r["pin"], r["pout"])
        e["calls"] += r["calls"]
    out = []
    for i in range(days):
        day = (date.today() - timedelta(days=days - 1 - i)).isoformat()
        e = by_day.get(day, {"cost": 0.0, "calls": 0})
        out.append({"date": day, "cost": round(e["cost"], 4), "calls": e["calls"]})
    return out


def dashboard(budget_monthly: float = 40.0) -> dict:
    """Alles für den Admin-LLM-Kosten-Tab (Design 21a): per-Feature-Aggregat +
    30-Tage-Kostenverlauf, Kosten diesen Monat mit linearer Hochrechnung auf den
    Restmonat, Aufrufe/⌀ der letzten 30 Tage, Budget-Prozent + Ampel."""
    import calendar
    from datetime import date

    base = summary()
    series = cost_timeseries(30)
    calls_30 = sum(d["calls"] for d in series)
    cost_30 = round(sum(d["cost"] for d in series), 4)

    today = date.today()
    # „diesen Monat“ = 1. bis heute (die letzten today.day Tage decken das ab).
    month_days = calendar.monthrange(today.year, today.month)[1]
    month_series = cost_timeseries(today.day)
    cost_month = round(sum(d["cost"] for d in month_series), 4)
    projected = round(cost_month / today.day * month_days, 2) if today.day else cost_month

    pct = round(100 * cost_month / budget_monthly) if budget_monthly > 0 else 0
    level = "ok" if pct < 80 else "warn" if pct < 100 else "over"

    return {
        **base,
        "series": series,
        "cost_month": cost_month,
        "projected_month": projected,
        "calls_30d": calls_30,
        "avg_cost_per_call": round(cost_30 / calls_30, 4) if calls_30 else 0.0,
        "budget_monthly": budget_monthly,
        "budget_pct": pct,
        "budget_level": level,
    }
