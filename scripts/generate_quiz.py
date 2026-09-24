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

from council import places, quiz  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
N_THEMES = 12          # so viele große Themen (Entitäten mit den meisten Beschlüssen)
THEME_MIN_DECISIONS = 8
OVERORDER = 2          # so viele Kandidaten je fehlender Frage bestellen …
OVERORDER_MIN = 4      # … aber nie weniger als diese


def _areas(store: CouncilStore) -> list[dict]:
    """Alle freigegebenen Katalogorte + Top-Themen (Entitäten)."""
    areas = [{"area_type": "district", "area_key": place.name,
              "label": f"{places.kind_label(place.kind)} {place.name}",
              "place_name": place.name, "place_id": place.id, "slug": None}
             for place in store.all_places() if place.quiz_enabled]
    themes = 0
    for e in store.list_entities(limit=400):
        if themes >= N_THEMES:
            break
        if e["kind"] in ("project", "place", "organisation") and (e.get("n") or 0) >= THEME_MIN_DECISIONS:
            areas.append({"area_type": "topic", "area_key": e["slug"], "label": e["name"], "slug": e["slug"]})
            themes += 1
    # Aus den letzten Sitzungen (Plan Q10): ein eigenes Gebiet, Quelle sind
    # die jüngsten Beschlüsse statt Wikipedia/Stadt-Seite.
    areas.append({"area_type": quiz.RECENT_AREA[0], "area_key": quiz.RECENT_AREA[1],
                  "label": "den jüngsten Sitzungen des Oldenburger Rats und seiner Ausschüsse",
                  "slug": None, "recent": True})
    return areas


def _sources(area: dict, facts: str) -> tuple[str, str, str]:
    """Quelltext (+ Haupt-Quelltyp/-ref) für ein Gebiet zusammenstellen.
    Netzabruf (Wikipedia/Stadt) — läuft im Worker-Thread."""
    if area.get("recent"):
        return f"Beschlüsse der jüngsten Sitzungen:\n{facts}", "ratsinfo", ""
    parts: list[str] = []
    src_type, src_ref = "ratsinfo", ""
    place_name = area.get("place_name") or area["label"]
    wiki = quiz.fetch_wikipedia(place_name)
    if wiki:
        parts.append(f"Wikipedia:\n{wiki[0]}")
        src_type, src_ref = "wikipedia", wiki[1]
    stadt = quiz.fetch_stadt_text(place_name)
    if stadt:
        parts.append(f"Stadt Oldenburg (oldenburg.de):\n{stadt[0]}")
        if not wiki:
            src_type, src_ref = "city", stadt[1]
    if facts:
        parts.append(f"Aktuelle Beschlüsse des Stadtrats:\n{facts}")
    return "\n\n".join(parts), src_type, src_ref


def _gen(area: dict, facts: str, n: int, verify: bool, existing: list[str] | None = None) -> dict:
    try:
        sources, src_type, src_ref = _sources(area, facts)
        rows = quiz.generate_for_area(
            area["area_type"], area["area_key"], area["label"], sources,
            n=n, source_type=src_type, source_ref=src_ref, verify=verify,
            existing=existing,
            # Die jüngsten Sitzungen SIND Ratspolitik — dort kein Deckel.
            council_share=1.0 if area.get("recent") else quiz.MAX_COUNCIL_SHARE)
        return {"status": "ok", "label": area["label"], "rows": rows}
    except Exception as exc:  # noqa: BLE001 — Einzelfehler ausweisen, weiterlaufen
        return {"status": "failed", "label": area["label"], "error": repr(exc)}


def process(council_db: Path, target: int = 10, per_run: int = 8, workers: int = 3,
            limit: int | None = None, verify: bool = True) -> dict:
    store = CouncilStore(council_db)
    # „Aktuell" nur, solange es aktuell ist: ältere Fragen dort mustern wir
    # aus — die Lücke füllt derselbe Lauf mit Fragen zu neueren Sitzungen.
    from datetime import datetime, timedelta
    cutoff = (datetime.utcnow() - timedelta(days=quiz.RECENT_MAX_DAYS)).isoformat(timespec="seconds")
    stale = store.retire_stale_quiz_area(*quiz.RECENT_AREA, cutoff)
    if stale:
        print(f"{stale} Frage(n) aus „Aus den letzten Sitzungen“ ausgemustert (älter als "
              f"{quiz.RECENT_MAX_DAYS} Tage).", flush=True)
    counts = store.quiz_area_counts()
    missing = {(a["area_type"], a["area_key"]): target - counts.get((a["area_type"], a["area_key"]), 0)
               for a in _areas(store)}
    # Bestellt wird mehr, als fehlt, gespeichert höchstens, was fehlt: Richter,
    # Dubletten- und Ratspolitik-Deckel lassen gemessen (23.09.2026, drei
    # Stadtteile) nur jede vierte bis fünfte Frage durch. Genau die fehlende
    # Zahl zu bestellen hieß, dass ein Gebiet mit einer Lücke Woche für Woche
    # eine Frage anforderte und keine bekam.
    areas = [
        (a, min(per_run, max(OVERORDER_MIN, OVERORDER * missing[(a["area_type"], a["area_key"])])))
        for a in _areas(store)
        if missing[(a["area_type"], a["area_key"])] > 0
    ]
    if limit:
        areas = areas[:limit]
    print(f"{len(areas)} Gebiet(e) unter Ziel {target}, bis {workers} Worker.", flush=True)

    # Ratsdaten-Kontext je Gebiet vorab (Main-Thread, DB-Lesen).
    facts = {a["area_key"]: (quiz.recent_facts(store) if a.get("recent") else quiz.council_facts(
                store, place_id=a.get("place_id"), slug=a["slug"])) for a, _ in areas}
    # Was das Gebiet schon fragt (auch Ausgemustertes) — gegen Umformulierungen.
    existing = {a["area_key"]: store.quiz_questions_of_area(a["area_type"], a["area_key"])
                for a, _ in areas}

    saved = failed = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(_gen, a, facts[a["area_key"]], requested, verify, existing[a["area_key"]]): a
            for a, requested in areas
        }
        for done, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            if r["status"] == "failed":
                failed += 1
                print(f"  [{done}/{len(areas)}] {r['label']}: FAILED {r['error']}", flush=True)
                continue
            area = futs[fut]
            gap = missing[(area["area_type"], area["area_key"])]
            best = sorted(r["rows"], key=lambda row: -(row.get("appeal") or 0))[:gap]
            n = store.save_quiz_questions(best)
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
