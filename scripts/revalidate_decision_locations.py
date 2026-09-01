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
    ortsbezug_ist_beiwerk,
    valid_llm_location,
)
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


DETERMINISTIC_METHODS = {"regex", "district_list", "place_catalog", "building_pattern"}


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


def beiwerk_links(store: CouncilStore) -> list[dict]:
    """Ortsbezüge, die nur Beiwerk eines stadtweiten Vorgangs sind.

    Die Regel greift beim Extrahieren; Bestandsdaten muss dieser Lauf
    nachziehen. Auf dem Prod-Bestand (01.09.2026) waren es 202 Zuordnungen an
    72 Beschlüssen — „Oldenburg Pass – Bericht" über die Adresse der VWG,
    „Marktgebührensatzung" über die Weser-Ems-Halle.
    """
    place_catalog = store.all_places()
    rows = store._conn.execute(
        """SELECT dl.decision_id, dl.location_slug, dl.source, l.name, d.title
             FROM council_decision_locations dl
             JOIN council_locations l ON l.slug = dl.location_slug
             JOIN council_decisions d ON d.id = dl.decision_id
            WHERE d.kind = 'decision'
            ORDER BY dl.decision_id DESC, l.name"""
    ).fetchall()
    return [dict(row) for row in rows
            if ortsbezug_ist_beiwerk(row["title"],
                                     {"name": row["name"], "source": row["source"]},
                                     catalog_places=place_catalog)]


def deterministic_changes(
    store: CouncilStore,
    *,
    ignored_current: set[tuple[int, str]] | None = None,
) -> tuple[list[dict], list[dict]]:
    decisions = store._conn.execute(
        "SELECT id,title,official_text FROM council_decisions WHERE kind='decision'"
    ).fetchall()
    expected: dict[int, dict[str, dict]] = {}
    place_catalog = store.all_places()
    for decision in decisions:
        rows = extract_explicit_locations(
            decision["title"] or "", source="title", catalog_places=place_catalog)
        rows += extract_explicit_locations(
            decision["official_text"] or "", source="official_text", catalog_places=place_catalog)
        for row in rows:
            slug = location_slug(row["name"])
            old = expected.setdefault(decision["id"], {}).get(slug)
            if old is None or row["confidence"] > old["confidence"]:
                expected[decision["id"]][slug] = row

    current_rows = store._conn.execute(
        "SELECT decision_id,location_slug,method FROM council_decision_locations"
    ).fetchall()
    ignored_current = ignored_current or set()
    current = {
        (row["decision_id"], row["location_slug"])
        for row in current_rows
        if (row["decision_id"], row["location_slug"]) not in ignored_current
    }
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
    beiwerk_rows = beiwerk_links(store)
    # Ein ungültiger LLM-Link kann denselben Ortsschlüssel wie ein gültiger
    # Regex-Fund tragen. Da der LLM-Link gleich entfernt wird, darf er bei der
    # Ermittlung fehlender deterministischer Links nicht mehr als vorhanden
    # gelten; sonst wäre für die Reparatur ein zweiter Lauf nötig.
    removed_llm_keys = {
        (row["decision_id"], row["location_slug"])
        for row in llm_rows
    }
    deterministic_rows, additions = deterministic_changes(
        store, ignored_current=removed_llm_keys)
    if apply and (llm_rows or beiwerk_rows or deterministic_rows or additions):
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
            store._conn.executemany(
                "DELETE FROM council_decision_locations "
                "WHERE decision_id=? AND location_slug=?",
                [(row["decision_id"], row["location_slug"]) for row in beiwerk_rows],
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
        # Die Ableitungen laufen NACH dem Aufräumen: Ein Ort, dem gerade sein
        # letzter Beschluss genommen wurde, braucht keinen Stadtteil mehr — und
        # ein neu angelegter hat noch keinen.
        store.backfill_location_place_ids()
        store.backfill_location_districts()
        store.backfill_location_districts_from_name()
    store.close()
    removed = len(llm_rows) + len(deterministic_rows) + len(beiwerk_rows) if apply else 0
    return {"invalid_llm": len(llm_rows), "invalid_deterministic": len(deterministic_rows),
            "beiwerk": len(beiwerk_rows),
            "additions": len(additions), "removed": removed,
            "examples": llm_rows[:15], "deterministic_examples": deterministic_rows[:20],
            "beiwerk_examples": beiwerk_rows[:20]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    stats = process(args.db, apply=args.apply)
    print("Ortslinks: " + ", ".join(f"{key}={stats[key]}" for key in
          ("invalid_llm", "invalid_deterministic", "beiwerk", "additions", "removed")))
    for row in stats["examples"]:
        print(f"  {row['decision_id']} | {row['name']} | {row['title']}")
    for row in stats["deterministic_examples"]:
        print(f"  deterministic | {row['decision_id']} | "
              f"{row['location_slug']} | {row['method']}")
    for row in stats["beiwerk_examples"]:
        print(f"  beiwerk | {row['decision_id']} | {row['name']} | {(row['title'] or '')[:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
