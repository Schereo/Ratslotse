#!/usr/bin/env python3
"""Weekly enrichment run — keeps the derived data fresh as new decisions arrive.

The daily protocol cron classifies, extracts € amounts, assesses goals and rebuilds
the FTS index. But the *LLM/embedding* enrichments behind the Themen pages, maps,
press links and "Ähnliche Beschlüsse" are heavier and run here, once a week, in order:

     1. Entitäten (NER)        extract_entities.py         — rebuilds council_entities
     2. Beschreibungen         describe_entities.py        — fills missing descriptions (slug-keyed meta survives the rebuild)
     2b. Vagheits-Urteile      warm_topic_vagueness.py     — beurteilt neue Vorschlags-Kandidaten vorab (sonst im Web-Request)
     3. Geocoding              geocode_entities.py         — geocodes new place entities
    3b. Straßen-Geometrie     strassen_snapshot.py        — alle benannten Wege in EINEM Overpass-Aufruf, dann lokal abgleichen
     4. Embeddings/Ähnliche    embed_decisions.py          — re-embeds for "Ähnliche Beschlüsse"
     5. Verwandte Themen       build_entity_relations.py   — "Hängt zusammen mit…" je Entität
     6. Themen ↔ Beschlüsse    match_topics_decisions.py   — matcht Nutzer-Themen gegen Beschlüsse
     7. Themenfeld-Rückblicke  generate_field_recaps.py    — LLM-Kurzrückblick je Politikfeld (≈ monatlich)
     8. Einfach erklärt        generate_simple_summaries.py — 500er-Wochentranche, neueste zuerst
     9. Personen-Stammdaten    backfill_stammdaten.py      — Mandate/Ausschuss-Besetzungen aus dem Ratsinfo
    10. Tragweite              rate_impact.py              — 500er-Tranche, VOR dem Wichtigkeits-Score
    11. Wichtigkeits-Score     score_importance.py         — mischt Tragweite + Gesprächswert (kein LLM)
    12. Quizfragen             generate_quiz.py            — füllt Gebiete unter Ziel-Fragenzahl auf
    13. Interessantheit        rate_interest.py            — 500er-Tranche, speist das Fundstück
    14. Fundstücke             generate_fundstuecke.py     — 21 Tage Vorlauf, idempotent

Diese Liste MUSS zu STEPS unten passen. Sie stand zuletzt auf sieben Einträgen mit
einer Lücke in der Nummerierung (1,2,3,5,5b,6,7), während STEPS längst vierzehn hatte —
wer danach die Laufzeit oder die LLM-Kosten abschätzte, lag um die Hälfte daneben.

Each step runs independently — a failure in one does NOT stop the others. Steps 2–3
are idempotent (only-missing); 1, 4, 5 are full rebuilds (cheap enough weekly).
Schritt 5 braucht 1 und 4 (liest die neu abgeleiteten Entitäten samt Embeddings),
Schritt 10 muss vor 11 laufen, damit die 50/50-Mischung frische Werte sieht.

Cron (Sundays 03:00):
    0 3 * * 0 cd ~/app && .venv/bin/python scripts/weekly_enrich.py >> ~/app/data/weekly_enrich.log 2>&1
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")  # für die Alert-Mail (RESEND_API_KEY, ALERT_EMAIL)

from kern.alerts import SCHRITTE_SCHLUESSEL, JobFehler  # noqa: E402

STEPS: list[tuple[str, str]] = [
    ("Entitäten (NER)", "extract_entities.py"),
    ("Beschreibungen", "describe_entities.py"),
    # Vagheits-Urteile der Vorschlags-Kandidaten VORRECHNEN (LLM, nur fehlende):
    # Sonst beurteilt der Assistent sie im Web-Request, und Schritt 3 steht
    # nach jeder Entitäten-Neuberechnung sekundenlang leer. Nach den
    # Beschreibungen, weil das Urteil sie mit liest.
    ("Vagheits-Urteile", "warm_topic_vagueness.py"),
    ("Geocoding", "geocode_entities.py"),
    # Straßen sind der Sonderfall: Overpass erlaubt dieser IP zwei Abfragen
    # gleichzeitig („Rate limit: 2"), und 500 Einzelabfragen ernten 429/504 —
    # gemessen am 03.09.2026, als ein Reparaturlauf 498 von 513 Straßen still
    # mit einem Nominatim-Einzelsegment abspeiste. EIN Aufruf holt alle 6.534
    # benannten Wege Oldenburgs; der Abgleich läuft danach ohne Netz. Damit
    # reparieren sich auch neu dazugekommene Straßen von selbst.
    ("Straßen-Geometrie", "strassen_snapshot.py aktualisieren"),
    ("Embeddings / Ähnliche", "embed_decisions.py"),
    # Anlagen (Task 33): Volltexte NEUER Anlagen nachladen (Netz+pypdf, kein
    # LLM; der Alt-Bestand kam per Einmal-Batch) und ihre Chunk-Vektoren für
    # den Anlagen-Kanal der Gründlichen Recherche schreiben (hash-idempotent).
    ("Anlagen-Texte", "backfill_anlagen_texte.py --limit 300"),
    ("Anlagen-Embeddings", "embed_anlagen.py"),
    # "Hängt zusammen mit…" je Thema (kein LLM, Sekunden) — muss NACH dem
    # Entitäten-Rebuild und den Embeddings laufen, es liest beide.
    ("Verwandte Themen", "build_entity_relations.py"),
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


def main() -> list[dict]:
    """Läuft alle Schritte durch und gibt je Schritt ein Protokoll zurück.

    **Warum je Schritt und nicht nur die Gescheiterten.** Bis 09/2026 gab es
    hier nur die Namen der Fehlschläge, und in der Cron-Übersicht stand
    entsprechend eine einzige Zahl („16 Schritte, 0 fehlgeschlagen"). Welcher
    Schritt zwei Stunden brauchte und welcher stumm nichts tat, sah man nur im
    Log auf dem Server — obwohl der Lauf es die ganze Zeit wusste. 16 der 18
    Schritte rufen kein ``run_guarded``, schreiben also auch keine eigene
    ``job_runs``-Zeile; ihre Bilanz kann nur von hier kommen.

    Ein Eintrag ist ``{"name", "script", "status", "duration_s"}``; ``status``
    ist ``ok`` oder ``error``. Falsy bei Erfolg ist die Rückgabe damit nicht
    mehr — ``_guarded_main`` wertet sie aus, und ``__main__`` ruft nur den.
    """
    protokoll: list[dict] = []
    for name, script in STEPS:
        print(f"\n=== {name} ({script}) ===", flush=True)
        start = time.monotonic()
        status = "ok"
        try:
            # Der Step-String darf Argumente tragen ("rate_interest.py --limit 500").
            parts = script.split()
            r = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / parts[0]), *parts[1:]], cwd=str(ROOT)
            )
            if r.returncode != 0:
                status = "error"
                print(f"!! {name} fehlgeschlagen (exit {r.returncode}) — weiter mit dem Rest.", flush=True)
        except Exception as exc:  # noqa: BLE001 — never let one step abort the run
            status = "error"
            print(f"!! {name} abgebrochen: {exc!r}", flush=True)
        protokoll.append({"name": name, "script": script, "status": status,
                          "duration_s": round(time.monotonic() - start, 1)})
    failed = [s["name"] for s in protokoll if s["status"] == "error"]
    print(f"\n=== weekly_enrich fertig — {len(STEPS) - len(failed)}/{len(STEPS)} ok"
          + (f", fehlgeschlagen: {', '.join(failed)}" if failed else "") + " ===", flush=True)
    return protokoll


def _guarded_main() -> dict:
    """main() meldet Teil-Fehler über die Rückgabe, nicht per Exception — für
    den Alert-Weg (run_guarded) in eine Exception übersetzen. Bei Erfolg sind
    die Kennzahlen die Schritt-Bilanz für die Cron-Übersicht.

    Der Fehlerfall trägt sie seit 09/2026 **mit** (``JobFehler``): Vorher warf
    dieser Weg ein nacktes ``RuntimeError``, und ``run_guarded`` verwarf die
    Kennzahlen bei jeder Exception — ausgerechnet am Tag eines Fehlschlags
    stand in ``job_runs`` also nur „error".
    """
    protokoll = main()
    # NUR die Liste, keine abgeleiteten Zahlen daneben. Bis 09/2026 standen
    # hier zusätzlich „Schritte gesamt" und „davon fehlgeschlagen" — im Panel
    # als zwei Chips, direkt über der Zeile „18 Schritte · 1 fehlgeschlagen",
    # die dasselbe sagt. Zwei Darstellungen einer Zahl können auseinanderlaufen;
    # die Liste ist die Quelle, das Zählen macht, wer sie anzeigt.
    kennzahlen = {SCHRITTE_SCHLUESSEL: protokoll}
    failed = [s["name"] for s in protokoll if s["status"] == "error"]
    if failed:
        raise JobFehler(
            "mindestens ein Teil-Schritt ist fehlgeschlagen (Details im Log): "
            + ", ".join(failed), kennzahlen)
    return kennzahlen


if __name__ == "__main__":
    from kern.alerts import run_guarded

    run_guarded("weekly_enrich", _guarded_main)
