#!/usr/bin/env python3
"""Wie ging dieselbe Sache in den anderen Städten aus?

**Die Frage am Abend vor der Sitzung.** Oldenburg hat die
Zweckentfremdungssatzung vertagt, die Grundsteuer C berichtet, die
Verpackungssteuer geprüft. Wer darüber spricht, will wissen: Was haben die
anderen daraus gemacht? Der Städtevergleich beantwortet bisher nur die
Gegenrichtung („was fehlt uns?").

```bash
python scripts/cities_gegenrichtung.py --kvonr 29787     # eine Oldenburger Vorlage
python scripts/cities_gegenrichtung.py --suche Zweckentfremdung
python scripts/cities_gegenrichtung.py --offen           # vertagte/verwiesene seit 2024
python scripts/cities_gegenrichtung.py                   # alle mit fremdem Gegenstück
```

**Was hier NICHT steht, und warum.** Der Plan sah einen Annotator vor, der aus
den Protokollen liest, WARUM ein Antrag anderswo scheiterte. Gemessen am
09.09.2026: Von 508 fremden Vorlagen in gemeinsamen Clustern tragen **44**
einen Ergebnistext, der länger ist als ein Etikett — und auch diese 44 sagen
nur „einstimmig geändert beschlossen" oder „von der Tagesordnung abgesetzt".
``resolutionText`` liefert **keine** der sechs Schnittstellen.

Die Begründung steht in den Protokollen, und die geben die
Ratsinformationssysteme nicht als Objekt heraus. Ein Annotator hätte für
neunzig Prozent der Fälle „unbekannt" geliefert. Das Ergebnis samt Gremium und
Datum steht dagegen da — und es beantwortet die Frage schon zum guten Teil.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from council.cities import default_paths  # noqa: E402
from council.cities.clusters import CLUSTER_VERSION  # noqa: E402
from council.cities.index import EMBED_MODEL  # noqa: E402
from council.cities.store import CitiesStore  # noqa: E402

#: Wie ein Ergebnis auf Deutsch heißt. Dieselben Werte wie ``model.Outcome``.
ERGEBNIS = {
    "accepted": "angenommen", "amended": "geändert beschlossen",
    "rejected": "abgelehnt", "postponed": "vertagt", "noted": "zur Kenntnis",
    "referred": "verwiesen", "withdrawn": "zurückgezogen", "none": "offen",
}


def oldenburger_papiere(main: CitiesStore, kvonr: int | None, suche: str | None,
                        nur_offen: bool) -> list[dict]:
    """Die Oldenburger Vorlagen, für die die Frage gestellt wird."""
    if kvonr:
        p = main.paper(f"oldenburg:paper:{kvonr}")
        return [p] if p else []

    # Alle Oldenburger Papiere, die in einem Cluster mit einer FREMDEN Stadt
    # liegen — ganze statische Anweisung, wie die Ideen-Abfragen.
    rows = main._conn.execute(
        "SELECT p.* FROM idea_clusters k "
        "JOIN papers p ON p.id = k.paper_id "
        "WHERE k.version = ? AND p.body_id = 'oldenburg' "
        "  AND EXISTS (SELECT 1 FROM idea_clusters k2 "
        "              JOIN papers p2 ON p2.id = k2.paper_id "
        "              WHERE k2.version = k.version AND k2.cluster_id = k.cluster_id "
        "                AND p2.body_id != 'oldenburg') "
        "ORDER BY p.date DESC", (CLUSTER_VERSION,))
    papiere = [dict(r) for r in rows]
    if suche:
        n = suche.lower()
        papiere = [p for p in papiere if n in (p.get("name") or "").lower()]
    if nur_offen:
        papiere = [p for p in papiere if _oldenburger_ergebnis(p) in
                   ("postponed", "referred", "rejected", "none")]
    return papiere


def _oldenburger_ergebnis(papier: dict) -> str:
    """Oldenburgs eigenes Ergebnis — aus der Rats-Datenbank, nicht aus OParl."""
    kvonr = (papier.get("id") or "").rsplit(":", 1)[-1]
    if not kvonr.isdigit():
        return "none"
    rats = sqlite3.connect(WURZEL / "data" / "council.sqlite")
    rats.row_factory = sqlite3.Row
    try:
        row = rats.execute(
            "SELECT d.outcome FROM council_decisions d "
            "JOIN council_sessions s ON s.ksinr = d.ksinr "
            "WHERE d.kvonr = ? ORDER BY s.session_date DESC LIMIT 1",
            (int(kvonr),)).fetchone()
        return (row["outcome"] if row else "none") or "none"
    finally:
        rats.close()


def zeigen(main: CitiesStore, papiere: list[dict], limit: int) -> int:
    gezeigt = 0
    for p in papiere:
        mitglieder = main.cluster_of(p["id"], EMBED_MODEL, CLUSTER_VERSION)
        fremde = [m for m in mitglieder if m["body_id"] != "oldenburg"]
        if not fremde:
            continue
        eigen = _oldenburger_ergebnis(p)
        print(f"\nOldenburg {(p.get('date') or '')[:7]}  [{ERGEBNIS.get(eigen, eigen)}]"
              f"  {(p.get('name') or '')[:74]}")
        for m in fremde[:6]:
            ergebnis = (main.outcome_for_paper(m["id"]) or {}).get("outcome") or "none"
            print(f"    {m['body_id'][:12]:13} {(m.get('date') or '')[:7]}  "
                  f"{ERGEBNIS.get(ergebnis, ergebnis):18} "
                  f"{(m.get('name') or '')[:62]}")
        gezeigt += 1
        if gezeigt >= limit:
            break
    if not gezeigt:
        print("Keine Oldenburger Vorlage mit fremdem Gegenstück gefunden.")
    return gezeigt


def main() -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    p.add_argument("--kvonr", type=int, help="eine bestimmte Oldenburger Vorlage")
    p.add_argument("--suche", help="nur Vorlagen, deren Titel das enthält")
    p.add_argument("--offen", action="store_true",
                   help="nur Oldenburger Vorlagen, die vertagt, verwiesen, "
                        "abgelehnt oder ohne Ergebnis sind — dort hilft der "
                        "Blick nach draußen am meisten")
    p.add_argument("--limit", type=int, default=20)
    a = p.parse_args()

    db, _f, _r = default_paths()
    store = CitiesStore(db)
    try:
        papiere = oldenburger_papiere(store, a.kvonr, a.suche, a.offen)
        print(f"{len(papiere)} Oldenburger Vorlage(n) mit gemeinsamer Idee.")
        zeigen(store, papiere, a.limit)
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
