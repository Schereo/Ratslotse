#!/usr/bin/env python3
"""Reproduzierbare Stichprobe produktiver Beschluss-Ortszuordnungen ausgeben.

Die Ausgabe ist JSONL und enthält neben Zuordnung und Konfidenz einen kurzen
Kontext um die gespeicherte Fundstelle. Damit lassen sich Precision-Stichproben
nach Extraktionsmethode prüfen, ohne vollständige Vorlagen zu exportieren.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.locations import (  # noqa: E402
    extract_explicit_locations,
    location_slug,
    valid_llm_location,
)


def _vorlage_text(conn: sqlite3.Connection, row: sqlite3.Row) -> str:
    lookups = [
        ("SELECT raw_text FROM council_vorlagen WHERE kvonr=? AND status='ok' LIMIT 1",
         (row["kvonr"],)),
        ("SELECT raw_text FROM council_vorlagen WHERE template_number=? AND status='ok' "
         "ORDER BY kvonr DESC LIMIT 1", (row["template_number"],)),
    ]
    for sql, args in lookups:
        if args[0] is None:
            continue
        hit = conn.execute(sql, args).fetchone()
        if hit and hit[0]:
            return str(hit[0])
    if row["template_number"]:
        hit = conn.execute(
            "SELECT raw_text FROM council_vorlagen WHERE status='ok' "
            "AND ? LIKE template_number || '/%' ORDER BY kvonr DESC LIMIT 1",
            (row["template_number"],),
        ).fetchone()
        if hit and hit[0]:
            return str(hit[0])
    return ""


def _snippet(text: str, evidence: str, radius: int = 260) -> str:
    clean = " ".join((text or "").split())
    needle = " ".join((evidence or "").split())
    pos = clean.casefold().find(needle.casefold()) if needle else -1
    if pos < 0:
        return clean[: radius * 2]
    start = max(0, pos - radius)
    end = min(len(clean), pos + len(needle) + radius)
    return ("…" if start else "") + clean[start:end] + ("…" if end < len(clean) else "")


def sample(conn: sqlite3.Connection, *, method: str, limit: int, seed: int,
           scope: str = "geocoded", context_radius: int = 260,
           current_rules: bool = False) -> list[dict]:
    where = ["dl.method = ?"]
    if scope == "geocoded":
        where.append("l.lat IS NOT NULL AND l.lon IS NOT NULL")
    elif scope == "district":
        where.append("l.district IS NOT NULL")
    rows = conn.execute(
        "SELECT dl.decision_id,dl.location_slug,dl.source,dl.evidence,dl.method,"
        "dl.confidence,l.name,l.kind,l.lat,l.lon,l.district,d.title,d.official_text,"
        "d.template_number,d.kvonr FROM council_decision_locations dl "
        "JOIN council_locations l ON l.slug=dl.location_slug "
        "JOIN council_decisions d ON d.id=dl.decision_id WHERE " + " AND ".join(where),
        (method,),
    ).fetchall()
    if current_rules and method == "llm":
        rows = [row for row in rows if valid_llm_location(
            row["name"], row["kind"], row["evidence"])]
    elif current_rules and method in {"regex", "stadtteilliste", "gebaeudemuster"}:
        checked = []
        for row in rows:
            text = row["title"] if row["source"] == "title" else row["official_text"]
            expected = {location_slug(item["name"])
                        for item in extract_explicit_locations(text or "", source=row["source"])}
            if row["location_slug"] in expected:
                checked.append(row)
        rows = checked
    rng = random.Random(f"{seed}:{method}:{scope}")
    chosen = rng.sample(rows, min(max(0, limit), len(rows)))
    result = []
    for row in chosen:
        source_text = {
            "title": row["title"] or "",
            "official_text": row["official_text"] or "",
            "vorlage": _vorlage_text(conn, row),
        }.get(row["source"], "")
        result.append({
            "decision_id": row["decision_id"],
            "title": row["title"],
            "location": row["name"],
            "kind": row["kind"],
            "method": row["method"],
            "source": row["source"],
            "evidence": row["evidence"],
            "context": _snippet(source_text, row["evidence"], radius=context_radius),
            "confidence": row["confidence"],
            "district": row["district"],
        })
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--method", required=True)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--scope", choices=("all", "geocoded", "district"), default="geocoded")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--take", type=int)
    ap.add_argument("--context-radius", type=int, default=260)
    ap.add_argument("--current-rules", action="store_true")
    args = ap.parse_args()
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = sample(conn, method=args.method, limit=args.limit, seed=args.seed,
                  scope=args.scope, context_radius=max(40, args.context_radius),
                  current_rules=args.current_rules)
    start = max(0, args.offset)
    rows = rows[start:start + args.take] if args.take is not None else rows[start:]
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
