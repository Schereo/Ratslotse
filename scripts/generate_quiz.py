#!/usr/bin/env python3
"""Quizfragen generieren — je Stadtteil und großem Thema.

Sammelt Quellen (Wikipedia, oldenburg.de, eigene Ratsdaten) und lässt das LLM
daraus Multiple-Choice-Fragen erzeugen; ein Verify-Pass behält nur belegte.
Idempotent: nur Gebiete UNTER der Ziel-Fragenzahl werden aufgefüllt — der Lauf
doppelt als wöchentliche Auffrischung und ersetzt ausgemusterte Fragen.

Netz/LLM laufen in einem kleinen Thread-Pool (schonend für Wikipedia); die
Ratsdaten-Kontexte werden vorab im Main-Thread geholt (SQLite ist nicht
thread-sicher), DB-Schreiben passiert im Main-Thread.

Usage::

    python scripts/generate_quiz.py                 # alle Gebiete bis Ziel auffüllen
    python scripts/generate_quiz.py --target 12 --workers 3
    python scripts/generate_quiz.py --limit 3       # Smoke-Test (3 Gebiete)
    python scripts/generate_quiz.py --no-verify     # ohne Verify-Pass (billiger)
"""
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import geo, quiz  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
N_THEMES = 12          # so viele große Themen (Entitäten mit den meisten Beschlüssen)
THEME_MIN_DECISIONS = 8


def _areas(store: CouncilStore) -> list[dict]:
    """Alle spielbaren Gebiete: 31 Stadtteile + Top-Themen (Entitäten)."""
    areas = [{"area_type": "stadtteil", "area_key": n, "label": f"Stadtteil {n}", "slug": None}
             for n in geo.stadtteile()]
    themes = 0
    for e in store.list_entities(limit=400):
        if themes >= N_THEMES:
            break
        if e["kind"] in ("projekt", "ort", "organisation") and (e.get("n") or 0) >= THEME_MIN_DECISIONS:
            areas.append({"area_type": "thema", "area_key": e["slug"], "label": e["name"], "slug": e["slug"]})
            themes += 1
    return areas


def _sources(area: dict, facts: str) -> tuple[str, str, str]:
    """Quelltext (+ Haupt-Quelltyp/-ref) für ein Gebiet zusammenstellen.
    Netzabruf (Wikipedia/Stadt) — läuft im Worker-Thread."""
    parts: list[str] = []
    src_type, src_ref = "ratsinfo", ""
    wiki = quiz.fetch_wikipedia(area["label"].replace("Stadtteil ", ""))
    if wiki:
        parts.append(f"Wikipedia:\n{wiki[0]}")
        src_type, src_ref = "wikipedia", wiki[1]
    stadt = quiz.fetch_stadt_text(area["label"].replace("Stadtteil ", ""))
    if stadt:
        parts.append(f"Stadt Oldenburg (oldenburg.de):\n{stadt[0]}")
        if not wiki:
            src_type, src_ref = "stadt", stadt[1]
    if facts:
        parts.append(f"Aktuelle Beschlüsse des Stadtrats:\n{facts}")
    return "\n\n".join(parts), src_type, src_ref


def _gen(area: dict, facts: str, n: int, verify: bool) -> dict:
    try:
        sources, src_type, src_ref = _sources(area, facts)
        rows = quiz.generate_for_area(
            area["area_type"], area["area_key"], area["label"], sources,
            n=n, source_type=src_type, source_ref=src_ref, verify=verify)
        return {"status": "ok", "label": area["label"], "rows": rows}
    except Exception as exc:  # noqa: BLE001 — Einzelfehler ausweisen, weiterlaufen
        return {"status": "failed", "label": area["label"], "error": repr(exc)}


def process(council_db: Path, target: int = 10, per_run: int = 8, workers: int = 3,
            limit: int | None = None, verify: bool = True) -> dict:
    store = CouncilStore(council_db)
    counts = store.quiz_area_counts()
    areas = [a for a in _areas(store)
             if counts.get((a["area_type"], a["area_key"]), 0) < target]
    if limit:
        areas = areas[:limit]
    print(f"{len(areas)} Gebiet(e) unter Ziel {target}, bis {workers} Worker.", flush=True)

    # Ratsdaten-Kontext je Gebiet vorab (Main-Thread, DB-Lesen).
    facts = {a["area_key"]: quiz.council_facts(
                store, stadtteil=None if a["slug"] else a["label"].replace("Stadtteil ", ""),
                slug=a["slug"]) for a in areas}

    saved = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_gen, a, facts[a["area_key"]], per_run, verify): a for a in areas}
        for done, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            if r["status"] == "failed":
                failed += 1
                print(f"  [{done}/{len(areas)}] {r['label']}: FAILED {r['error']}", flush=True)
                continue
            n = store.save_quiz_questions(r["rows"])
            saved += n
            print(f"  [{done}/{len(areas)}] {r['label']}: +{n} Fragen", flush=True)

    total = store.quiz_stats_total()
    store.close()
    return {"gebiete": len(areas), "neue_fragen": saved, "failed": failed,
            "fragen_gesamt": total["fragen"], "gebiete_gesamt": total["gebiete"]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--target", type=int, default=10, help="Ziel-Fragenzahl je Gebiet")
    ap.add_argument("--per-run", type=int, default=8, help="Fragen je LLM-Aufruf")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()

    stats = process(args.db, args.target, args.per_run, args.workers, args.limit, not args.no_verify)
    print(f"\n=== done: {stats['neue_fragen']} neue Fragen über {stats['gebiete']} Gebiete, "
          f"{stats['failed']} Fehler · Bestand: {stats['fragen_gesamt']} aktive Fragen "
          f"in {stats['gebiete_gesamt']} Gebieten ===")
    return 1 if stats["failed"] and not stats["neue_fragen"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
