#!/usr/bin/env python3
"""Bestehende LLM-Ortslinks gegen die aktuellen Präzisionsregeln prüfen.

Ohne ``--apply`` ist der Lauf read-only und zeigt nur Anzahl und Beispiele.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.locations import (  # noqa: E402
    extract_explicit_locations,
    location_slug,
    valid_llm_location,
)
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


DETERMINISTIC_METHODS = {"regex", "stadtteilliste", "gebaeudemuster"}


def invalid_llm_links(store: CouncilStore) -> list[dict]:
    rows = store._conn.execute(
        """SELECT dl.decision_id,dl.location_slug,dl.evidence,l.name,l.kind,d.title
           FROM council_decision_locations dl
           JOIN council_locations l ON l.slug=dl.location_slug
           JOIN council_decisions d ON d.id=dl.decision_id
           WHERE dl.method='llm'
           ORDER BY dl.decision_id DESC,l.name"""
    ).fetchall()
    return [dict(row) for row in rows
            if not valid_llm_location(row["name"], row["kind"], row["evidence"])]


def deterministic_changes(store: CouncilStore) -> tuple[list[dict], list[dict]]:
    decisions = store._conn.execute(
        "SELECT id,title,beschluss FROM council_decisions WHERE kind='decision'"
    ).fetchall()
    expected: dict[int, dict[str, dict]] = {}
    for decision in decisions:
        rows = extract_explicit_locations(decision["title"] or "", source="title")
        rows += extract_explicit_locations(decision["beschluss"] or "", source="beschluss")
        for row in rows:
            slug = location_slug(row["name"])
            old = expected.setdefault(decision["id"], {}).get(slug)
            if old is None or row["confidence"] > old["confidence"]:
                expected[decision["id"]][slug] = row

    current_rows = store._conn.execute(
        "SELECT decision_id,location_slug,method FROM council_decision_locations"
    ).fetchall()
    current = {(row["decision_id"], row["location_slug"]) for row in current_rows}
    invalid = [dict(row) for row in current_rows
               if row["method"] in DETERMINISTIC_METHODS
               and row["location_slug"] not in expected.get(row["decision_id"], {})]
    additions = []
    for decision_id, by_slug in expected.items():
        for slug, row in by_slug.items():
            if (decision_id, slug) not in current:
                additions.append({"decision_id": decision_id, "location_slug": slug, **row})
    return invalid, additions


def process(council_db: Path, *, apply: bool = False) -> dict:
    store = CouncilStore(council_db)
    llm_rows = invalid_llm_links(store)
    deterministic_rows, additions = deterministic_changes(store)
    if apply and (llm_rows or deterministic_rows or additions):
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with store._conn:
            store._conn.executemany(
                "DELETE FROM council_decision_locations "
                "WHERE decision_id=? AND location_slug=? AND method='llm'",
                [(row["decision_id"], row["location_slug"]) for row in llm_rows],
            )
            store._conn.executemany(
                "DELETE FROM council_decision_locations "
                "WHERE decision_id=? AND location_slug=?",
                [(row["decision_id"], row["location_slug"]) for row in deterministic_rows],
            )
            for row in additions:
                store._conn.execute(
                    "INSERT INTO council_locations(slug,name,kind,updated_at) VALUES (?,?,?,?) "
                    "ON CONFLICT(slug) DO UPDATE SET name=excluded.name,kind=excluded.kind,"
                    "updated_at=excluded.updated_at",
                    (row["location_slug"], row["name"], row["kind"], now),
                )
                store._conn.execute(
                    "INSERT OR IGNORE INTO council_decision_locations "
                    "(decision_id,location_slug,source,evidence,method,confidence,updated_at) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (row["decision_id"], row["location_slug"], row["source"],
                     row["evidence"][:500], row["method"], row["confidence"], now),
                )
    store.close()
    removed = len(llm_rows) + len(deterministic_rows) if apply else 0
    return {"invalid_llm": len(llm_rows), "invalid_deterministic": len(deterministic_rows),
            "additions": len(additions), "removed": removed,
            "examples": llm_rows[:15], "deterministic_examples": deterministic_rows[:20]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    stats = process(args.db, apply=args.apply)
    print("Ortslinks: " + ", ".join(f"{key}={stats[key]}" for key in
          ("invalid_llm", "invalid_deterministic", "additions", "removed")))
    for row in stats["examples"]:
        print(f"  {row['decision_id']} | {row['name']} | {row['title']}")
    for row in stats["deterministic_examples"]:
        print(f"  deterministic | {row['decision_id']} | "
              f"{row['location_slug']} | {row['method']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
