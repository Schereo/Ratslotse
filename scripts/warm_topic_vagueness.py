#!/usr/bin/env python3
"""Vagheits-Urteile für die Themen-Vorschläge VORRECHNEN — statt im Klick.

Der Vorschlags-Endpunkt (``/topics/suggestions``) lässt für jeden Kandidaten
einmal ein Modell entscheiden, ob der Name als Thema taugt („Kunstrasenplatz"
nein, „Kunstrasenplatz Kennedystraße" ja), und merkt sich das Urteil je Slug.
Was noch kein Urteil hat, wird IM WEB-REQUEST beurteilt — beim ersten Aufruf
nach einer Entitäten-Neuberechnung sind das Dutzende Aufrufe hintereinander,
und Schritt 3 des Einrichtungs-Assistenten stand sekundenlang leer (Tims
Befund, 02.09.2026; auf dev hatten 31 von 288 Kandidaten ein Urteil).

Dieses Skript holt das nach: alle Kandidaten, die der Endpunkt überhaupt
vorschlagen könnte (Orte und Vorhaben mit mindestens zwei Beschlüssen in drei
Jahren), ohne oder mit veraltetem Urteil. Idempotent — beim zweiten Lauf gibt
es nichts zu tun. Läuft wöchentlich nach den Beschreibungen (weekly_enrich),
weil das Urteil die Beschreibung mit liest.

    .venv/bin/python scripts/warm_topic_vagueness.py [--limit N] [--trocken]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from council import topic_intel  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"
#: Dasselbe weiteste Fenster wie der Assistent (LOCAL_WINDOW_DAYS[-1]).
TAGE = 1095
MINDESTENS_BESCHLUESSE = 2


def kandidaten(store: CouncilStore) -> list[dict]:
    """Was der Endpunkt vorschlagen könnte — stadtweit und je Ortsbereich."""
    rows = store._conn.execute(
        """SELECT e.slug, e.name, m.description
             FROM council_entities e
             JOIN council_entity_links el ON el.entity_id = e.id
             JOIN council_decisions d ON d.id = el.decision_id
             JOIN council_sessions cs ON cs.ksinr = d.ksinr
             LEFT JOIN council_entity_meta m ON m.slug = e.slug
            WHERE e.kind IN ('place', 'project')
              AND cs.session_date >= date('now', ?)
            GROUP BY e.id
           HAVING COUNT(DISTINCT el.decision_id) >= ?
            ORDER BY COUNT(DISTINCT el.decision_id) DESC""",
        (f"-{TAGE} day", MINDESTENS_BESCHLUESSE)).fetchall()
    return [dict(r) for r in rows]


def process(council_db: Path, *, limit: int | None = None, trocken: bool = False) -> dict:
    store = CouncilStore(council_db)
    try:
        alle = kandidaten(store)
        # Ein Urteil gilt für den Namen, unter dem es gefällt wurde — heißt die
        # Entität nach einer Neuberechnung anders, zählt es nicht mehr.
        vorhanden = store.topic_vagueness_verdicts([k["slug"] for k in alle])
        offen = [k for k in alle
                 if (vorhanden.get(k["slug"]) or {}).get("name") != (k["name"] or "").strip()]
        if limit:
            offen = offen[:limit]
        beurteilt = vage = fehler = 0
        for k in offen:
            name = (k["name"] or "").strip()
            if not name or topic_intel.looks_generic(name):
                continue   # der billige Filter greift vorher; kein Modell nötig
            if trocken:
                beurteilt += 1
                continue
            beschreibung = (k.get("description") or "").strip() or (
                f"Neue Beschlüsse, Planungen und Maßnahmen des Oldenburger Stadtrats rund um {name}.")
            try:
                urteil = topic_intel.check_vagueness(name, beschreibung)
                store.save_topic_vagueness(k["slug"], name, urteil)
            except Exception:  # noqa: BLE001 — ein hakender Aufruf soll den Rest nicht kosten
                fehler += 1
                continue
            beurteilt += 1
            vage += 1 if urteil.get("vague") else 0
        return {"kandidaten": len(alle), "offen": len(offen), "beurteilt": beurteilt,
                "vage": vage, "fehler": fehler}
    finally:
        store.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--trocken", action="store_true", help="nur zählen, kein Modell")
    args = ap.parse_args()
    stats = process(args.db, limit=args.limit, trocken=args.trocken)
    print("Vagheits-Urteile: " + ", ".join(f"{k}={v}" for k, v in stats.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
