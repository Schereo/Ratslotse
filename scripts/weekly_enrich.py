#!/usr/bin/env python3
"""Weekly enrichment run — keeps the derived data fresh as new decisions arrive.

The daily protocol cron classifies, extracts € amounts, assesses goals and rebuilds
the FTS index. But the *LLM/embedding* enrichments behind the Themen pages, maps,
press links and "Ähnliche Beschlüsse" are heavier and run here, once a week, in order:

    1. Entitäten (NER)        extract_entities.py   — rebuilds council_entities
    2. Beschreibungen          describe_entities.py  — fills missing descriptions (slug-keyed meta survives the rebuild)
    3. Geocoding               geocode_entities.py   — geocodes new place entities
    5. Embeddings/Ähnliche     embed_decisions.py    — re-embeds for "Ähnliche Beschlüsse"
    6. Themen ↔ Beschlüsse     match_topics_decisions.py — matcht Nutzer-Themen gegen Beschlüsse
    7. Themenfeld-Rückblicke   generate_field_recaps.py  — LLM-Kurzrückblick je Politikfeld (≈ monatlich)

Each step runs independently — a failure in one does NOT stop the others. Steps 2–3
are idempotent (only-missing); 1, 4, 5 are full rebuilds (cheap enough weekly).

Cron (Sundays 03:00):
    0 3 * * 0 cd ~/app && .venv/bin/python scripts/weekly_enrich.py >> ~/app/data/weekly_enrich.log 2>&1
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")  # für die Alert-Mail (RESEND_API_KEY, ALERT_EMAIL)

STEPS: list[tuple[str, str]] = [
    ("Entitäten (NER)", "extract_entities.py"),
    ("Beschreibungen", "describe_entities.py"),
    ("Geocoding", "geocode_entities.py"),
    ("Embeddings / Ähnliche", "embed_decisions.py"),
    ("Themen ↔ Beschlüsse", "match_topics_decisions.py"),
    ("Themenfeld-Rückblicke", "generate_field_recaps.py"),
    # „Einfach erklärt"-Kurzfassungen (RL-904): 500er-Wochentranche, neueste
    # zuerst — der Alt-Bestand seit 2018 füllt sich so über einige Wochen auf.
    ("Einfach erklärt", "generate_simple_summaries.py"),
    # Personen-/Gremien-Stammdaten aus dem Ratsinfo (kein LLM, ein paar hundert
    # Requests) — Mandatswechsel und neue Ausschuss-Besetzungen kommen so
    # spätestens nach einer Woche an.
    ("Personen-Stammdaten (Ratsinfo)", "backfill_stammdaten.py"),
    # Wichtigkeits-Score der Beschlüsse neu berechnen (kein LLM) — hebt wichtige
    # Beschlüsse in Listen und im Quiz hervor. Vor dem Quiz, damit dessen
    # „ratspolitik"-Fragen die frischen Scores nutzen.
    # Tragweite (RL-U16, LLM): 500er-Tranche VOR dem Wichtigkeits-Score,
    # damit die 50/50-Mischung frische Werte sieht.
    ("Tragweite", "rate_impact.py --limit 500"),
    ("Wichtigkeits-Score", "score_importance.py"),
    # Quizfragen auffüllen (LLM) — nur Gebiete unter Ziel-Fragenzahl, ersetzt
    # ausgemusterte Fragen und deckt neue Beschluss-Themen ab.
    ("Quizfragen", "generate_quiz.py"),
    # Interessantheit (RL-U11, LLM): 500er-Wochentranche, neueste zuerst —
    # speist das Fundstück des Tages; der Alt-Bestand füllt sich über Wochen.
    ("Interessantheit", "rate_interest.py --limit 500"),
    # Fundstücke 21 Tage im Voraus (nur fehlende Tage, idempotent).
    ("Fundstücke", "generate_fundstuecke.py --days 21"),
]


def main() -> list[str]:
    """Läuft alle Schritte durch und gibt die Namen der gescheiterten zurück
    (leere Liste = alles ok, wirkt als Exit-Code weiterhin falsy)."""
    failed: list[str] = []
    for name, script in STEPS:
        print(f"\n=== {name} ({script}) ===", flush=True)
        try:
            # Der Step-String darf Argumente tragen ("rate_interest.py --limit 500").
            parts = script.split()
            r = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / parts[0]), *parts[1:]], cwd=str(ROOT)
            )
            if r.returncode != 0:
                failed.append(name)
                print(f"!! {name} fehlgeschlagen (exit {r.returncode}) — weiter mit dem Rest.", flush=True)
        except Exception as exc:  # noqa: BLE001 — never let one step abort the run
            failed.append(name)
            print(f"!! {name} abgebrochen: {exc!r}", flush=True)
    print(f"\n=== weekly_enrich fertig — {len(STEPS) - len(failed)}/{len(STEPS)} ok"
          + (f", fehlgeschlagen: {', '.join(failed)}" if failed else "") + " ===", flush=True)
    return failed


def _guarded_main() -> dict:
    """main() meldet Teil-Fehler über die Rückgabe, nicht per Exception — für
    den Alert-Weg (run_guarded) in eine Exception übersetzen. Bei Erfolg sind
    die Kennzahlen die Schritt-Bilanz für die Cron-Übersicht."""
    failed = main()
    if failed:
        raise RuntimeError(
            "mindestens ein Teil-Schritt ist fehlgeschlagen (Details im Log): " + ", ".join(failed))
    return {"Schritte gesamt": len(STEPS), "davon fehlgeschlagen": 0}


if __name__ == "__main__":
    from nwz.alerts import run_guarded

    run_guarded("weekly_enrich", _guarded_main)
