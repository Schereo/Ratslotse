"""Lightweight LLM-usage tracking, so the admin page can show where the model spend
goes (tokens + estimated cost per feature).

Best-effort by design: recording must NEVER break an LLM call, and under write
contention (parallel backfills) a dropped row just means slightly under-counted stats.
Rows land in ``llm_usage`` in the shared ratslotse.sqlite.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "ratslotse.sqlite"

# $ per 1M tokens (input, output) — NUR noch der Schätz-Fallback für Zeilen
# ohne echten Kostenwert (alte Einträge, Provider ohne usage.cost). Neue
# Aufrufe tragen die ECHTEN OpenRouter-Kosten in cost_usd (kern/llm.py).
PRICES: dict[str, tuple[float, float]] = {
    "deepseek/deepseek-v4-pro": (0.435, 0.87),
    "deepseek/deepseek-v4-flash": (0.10, 0.20),
    "openai/gpt-4o": (2.5, 10.0),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "google/gemini-2.5-flash": (0.30, 2.50),
    "google/gemini-2.5-flash-lite": (0.10, 0.40),
    "meta-llama/llama-4-maverick": (0.15, 0.60),
    # Die Modelle aus dem Lotti-Vergleich (PR 29). Listenpreise von OpenRouter,
    # Stand 22.09.2026 — sie greifen nur für Zeilen OHNE cost_usd; jeder neue
    # Aufruf trägt die echten Kosten mit.
    "google/gemini-2.5-pro": (1.25, 10.0),
    "google/gemini-3.1-pro-preview": (2.0, 12.0),
    "google/gemini-3.8-flash": (0.75, 3.75),
    "anthropic/claude-sonnet-4.6": (3.0, 15.0),
    # Die Nachfolger von Gemini 2.5 (läuft am 20.10.2026 aus), Listenpreise
    # von OpenRouter am 23.09.2026. 3.5 Flash Lite kostet so viel wie 2.5
    # Flash, nicht wie 2.5 Flash Lite — „Lite" ist kein Preisschild.
    "google/gemini-3.1-flash-lite": (0.25, 1.50),
    "google/gemini-3.5-flash-lite": (0.30, 2.50),
    "google/gemini-3-flash-preview": (0.50, 3.00),
}


def _db() -> str:
    return os.environ.get("RATSLOTSE_SQLITE") or str(_DEFAULT_DB)


def _connect() -> sqlite3.Connection:
    # `data/` selbst anlegen: Bis zum Ausbau der Prompt-Overrides (08/2026) tat
    # das `kern/prompts.py::_connect` nebenbei, und zwar bei JEDEM Prompt-Abruf.
    # Auf einem frischen Checkout ohne `data/` wäre das hier sonst ein
    # „unable to open database file".
    pfad = Path(_db())
    if pfad.parent.name:
        pfad.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_db(), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS llm_usage ("
        "id INTEGER PRIMARY KEY, ts TEXT NOT NULL DEFAULT (datetime('now')), "
        "feature TEXT NOT NULL, model TEXT, prompt_tokens INTEGER, completion_tokens INTEGER, "
        "cost_usd REAL)")
    try:  # Bestands-DBs: Spalte nachrüsten (idempotent scheitern lassen)
        conn.execute("ALTER TABLE llm_usage ADD COLUMN cost_usd REAL")
    except sqlite3.OperationalError:
        pass
    return conn


def record(feature: str, model: str | None, prompt_tokens: int, completion_tokens: int,
           cost_usd: float | None = None) -> None:
    """Append one usage row. Swallows all errors — tracking is never load-bearing."""
    try:
        conn = _connect()
        with conn:
            conn.execute(
                "INSERT INTO llm_usage(feature, model, prompt_tokens, completion_tokens, cost_usd) "
                "VALUES (?,?,?,?,?)",
                (feature, model, int(prompt_tokens or 0), int(completion_tokens or 0), cost_usd))
        conn.close()
    except Exception:  # noqa: BLE001 — usage tracking must never break an LLM call
        pass


def jetzt_utc() -> str:
    """Der Zeitstempel, den ``ts`` gerade schreiben würde.

    ``ts`` steht als ``datetime('now')`` in der Tabelle, also UTC — wer mit
    einer lokalen Uhr dagegen vergleicht, greift in Deutschland zwei Stunden
    daneben (derselbe Fehler, den ``cost_timeseries`` unten mit
    ``date(ts,'localtime')`` einfängt). Deshalb gibt es die Marke hier und
    nicht an der Aufrufstelle.
    """
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def seit(feature: str, marke: str) -> dict:
    """Was ``feature`` seit der Zeitmarke ``marke`` (aus :func:`jetzt_utc`) kostete.

    Für Messläufe: Ein Eval merkt sich seinen Startzeitpunkt und fragt
    danach, was SEIN Lauf gekostet hat — die Summe über die ganze Tabelle
    trüge jeden früheren Lauf mit.

    ``ohne_kosten`` ist der wichtigste Wert im Rückgabe-dict: Es sind die
    Zeilen, für die der Provider **keinen** Kostenwert mitgeliefert hat. Ist
    die Zahl größer als 0, ist ``cost_usd`` eine UNTERGRENZE und darf nicht
    als Gesamtkosten ausgewiesen werden — eine Schätzung aus :data:`PRICES`
    wäre für einen Modellvergleich das falsche Werkzeug, weil sie genau das
    misst, was man von Hand eingetragen hat.
    """
    leer = {"calls": 0, "cost_usd": 0.0, "ohne_kosten": 0,
            "prompt_tokens": 0, "completion_tokens": 0, "models": []}
    try:
        conn = _connect()
        rows = conn.execute(
            "SELECT model, COUNT(*) calls, COALESCE(SUM(cost_usd),0) cost, "
            "SUM(CASE WHEN cost_usd IS NULL THEN 1 ELSE 0 END) ohne, "
            "COALESCE(SUM(prompt_tokens),0) pin, COALESCE(SUM(completion_tokens),0) pout "
            "FROM llm_usage WHERE feature = ? AND ts >= ? GROUP BY model",
            (feature, marke)).fetchall()
        conn.close()
    except Exception:  # noqa: BLE001 — Kostenmessung ist nie load-bearing
        return leer
    aus = dict(leer)
    modelle: list[str] = []
    for r in rows:
        aus["calls"] += r["calls"]
        aus["cost_usd"] += r["cost"]
        aus["ohne_kosten"] += r["ohne"]
        aus["prompt_tokens"] += r["pin"]
        aus["completion_tokens"] += r["pout"]
        if r["model"]:
            modelle.append(r["model"])
    aus["models"] = sorted(modelle)
    return aus


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
            "COALESCE(SUM(completion_tokens),0) pout, MIN(ts) first, MAX(ts) last, "
            # Echte Kosten wo vorhanden; für Zeilen ohne cost_usd (Altbestand,
            # Provider ohne Kostenfeld) die Token-Summen separat — die laufen
            # unten durch die PRICES-Schätzung.
            "COALESCE(SUM(cost_usd),0) creal, "
            "COALESCE(SUM(CASE WHEN cost_usd IS NULL THEN prompt_tokens END),0) pin_est, "
            "COALESCE(SUM(CASE WHEN cost_usd IS NULL THEN completion_tokens END),0) pout_est "
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
        f["cost"] += r["creal"] + _cost(r["model"], r["pin_est"], r["pout_est"])
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
    """Tägliche Kosten + Aufrufe der letzten ``days`` Tage — lückenlos
    (fehlende Tage = 0), ältester zuerst. Echte OpenRouter-Kosten (cost_usd) wo
    vorhanden; nur Zeilen ohne Kostenwert laufen durch die PRICES-Schätzung."""
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    try:
        conn = _connect()
        rows = conn.execute(
            # date(ts, 'localtime'), nicht date(ts): `ts` kommt aus SQLites
            # datetime('now') und ist damit UTC, verglichen wird aber gegen
            # date.today() — den LOKALEN Tag. In Deutschland (UTC+1/+2) fiel
            # die Kostenübersicht dadurch jede Nacht zwischen 0 und 2 Uhr auf
            # null zurück: Sie suchte einen Tag, den es in den Daten noch nicht
            # gab. In der CI läuft alles in UTC, dort sind beide gleich —
            # deshalb ist es erst am 17.08.2026 um 00:45 lokal aufgefallen.
            "SELECT date(ts, 'localtime') d, model, COUNT(*) calls, "
            "COALESCE(SUM(cost_usd),0) creal, "
            "COALESCE(SUM(CASE WHEN cost_usd IS NULL THEN prompt_tokens END),0) pin, "
            "COALESCE(SUM(CASE WHEN cost_usd IS NULL THEN completion_tokens END),0) pout "
            "FROM llm_usage WHERE date(ts, 'localtime') >= ? "
            "GROUP BY date(ts, 'localtime'), model",
            (since,)).fetchall()
        conn.close()
    except Exception:  # noqa: BLE001
        return []
    by_day: dict[str, dict] = {}
    for r in rows:
        e = by_day.setdefault(r["d"], {"cost": 0.0, "calls": 0})
        e["cost"] += r["creal"] + _cost(r["model"], r["pin"], r["pout"])
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
