#!/usr/bin/env python3
"""Weekly enrichment run — keeps the derived data fresh as new decisions arrive.

The daily protocol cron classifies, extracts € amounts, assesses goals and rebuilds
the FTS index. But the *LLM/embedding* enrichments behind the Themen pages, maps,
press links and "Ähnliche Beschlüsse" are heavier and run here, once a week, in order:

    1. Entitäten (NER)        extract_entities.py   — rebuilds council_entities
    2. Beschreibungen          describe_entities.py  — fills missing descriptions (slug-keyed meta survives the rebuild)
    3. Geocoding               geocode_entities.py   — geocodes new place entities
    4. Presse-Links            link_news.py          — re-matches decisions ↔ NWZ
    5. Embeddings/Ähnliche     embed_decisions.py    — re-embeds for "Ähnliche Beschlüsse"
    6. Verwandte Themen        build_entity_relations.py — "Hängt zusammen mit…" je Entität
    7. Themen ↔ Beschlüsse     match_topics_decisions.py — matcht Nutzer-Themen gegen Beschlüsse
    8. Themenfeld-Rückblicke   generate_field_recaps.py  — LLM-Kurzrückblick je Politikfeld (≈ monatlich)

Each step runs independently — a failure in one does NOT stop the others. Steps 2–3
are idempotent (only-missing); 1, 4, 5, 6 are full rebuilds (cheap enough weekly).
Step 6 must follow 1 and 5 — it reads the rebuilt entities and their embeddings.

Cron (Sundays 03:00):
    0 3 * * 0 cd ~/app && .venv/bin/python scripts/weekly_enrich.py >> ~/app/data/weekly_enrich.log 2>&1
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STEPS: list[tuple[str, str]] = [
    ("Entitäten (NER)", "extract_entities.py"),
    ("Beschreibungen", "describe_entities.py"),
    ("Geocoding", "geocode_entities.py"),
    ("Presse-Links", "link_news.py"),
    ("Embeddings / Ähnliche", "embed_decisions.py"),
    ("Verwandte Themen", "build_entity_relations.py"),
    ("Themen ↔ Beschlüsse", "match_topics_decisions.py"),
    ("Themenfeld-Rückblicke", "generate_field_recaps.py"),
]


def main() -> int:
    failed: list[str] = []
    for name, script in STEPS:
        print(f"\n=== {name} ({script}) ===", flush=True)
        try:
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / script)], cwd=str(ROOT))
            if r.returncode != 0:
                failed.append(name)
                print(f"!! {name} fehlgeschlagen (exit {r.returncode}) — weiter mit dem Rest.", flush=True)
        except Exception as exc:  # noqa: BLE001 — never let one step abort the run
            failed.append(name)
            print(f"!! {name} abgebrochen: {exc!r}", flush=True)
    print(f"\n=== weekly_enrich fertig — {len(STEPS) - len(failed)}/{len(STEPS)} ok"
          + (f", fehlgeschlagen: {', '.join(failed)}" if failed else "") + " ===", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
