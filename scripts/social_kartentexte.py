#!/usr/bin/env python3
"""Kartentexte für Social Media schreiben — ein Satz je Tagesordnungspunkt.

Der dritte Text neben Kurzfassung und Tragweite-Grund, und der einzige, der
die **ganze Vorlage samt Anlagen** sieht. Warum das nötig ist, steht in
``council/social_text.py``; kurz: Die Kurzfassung kennt nur den Titel, der
Tragweite-Grund wertet (er begründet eine Rangfolge).

Läuft täglich HINTER ``rate_agenda_impact.py``: Geschrieben wird nur für
Punkte, die schon eine Tragweite haben und damit überhaupt auf eine Karte
kommen können — rund 20 der 87 öffentlichen Punkte einer Woche::

    python scripts/social_kartentexte.py --limit 40
    python scripts/social_kartentexte.py --probe 5      # nur zeigen, nichts speichern

Bereits Geschriebenes wird nie erneut bezahlt (Tabelle
``agenda_item_social``, Schlüssel ksinr + item_number).
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.social_text import kontext, text_fuer  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def _mit_anlagen(store: CouncilStore, punkte: list[dict]) -> list[tuple[dict, list[dict]]]:
    """Zu jedem Punkt seine Anlagen — in EINEM Rutsch, vor den Threads.

    SQLite-Verbindungen gehören einem Thread; die Aufrufe danach laufen
    parallel, die Datenbank nicht.
    """
    return [(p, store.anlagen_fuer(p["kvonr"]) if p.get("kvonr") else []) for p in punkte]


def _dringlichkeit_nachladen(punkt: dict) -> None:
    """Beim Dringlichkeitsantrag steht der Inhalt NUR im PDF.

    Er hat keine Vorlage — ohne diesen Griff bliebe dem Modell der
    Dateiname. Und der heißt manchmal einfach „Dringlichkeitsantrag".
    Best effort: Ein kaputtes PDF kostet den Text, nicht den Lauf.
    """
    if punkt.get("raw_text"):
        return
    if not str(punkt.get("item_number", "")).startswith("DZT"):
        return
    # Der Scraper legt den Text beim Einlesen ab; hier steht nur der Rückfall
    # für Sitzungen, die vor dieser Änderung eingelesen wurden.
    if punkt.get("anlage_text"):
        punkt["raw_text"] = punkt["anlage_text"]
        return
    if not punkt.get("anlage_url"):
        return
    try:
        from council.vorlagen import _pdf_text  # noqa: PLC0415

        text, _seiten = _pdf_text(punkt["anlage_url"])
        punkt["raw_text"] = text
    except Exception as fehler:  # noqa: BLE001
        print(f"  {punkt['item_number']}: PDF nicht lesbar ({fehler})", file=sys.stderr)


def process(db_path: Path, limit: int | None, tage: int, workers: int,
            mindest_wichtig: int) -> tuple[int, int]:
    store = CouncilStore(db_path)
    try:
        todo = _mit_anlagen(store, store.agenda_items_needing_social_text(
            limit, tage_voraus=tage, mindest_wichtig=mindest_wichtig))
        for punkt, _ in todo:
            _dringlichkeit_nachladen(punkt)
        geschrieben = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            ergebnisse = pool.map(lambda pa: (pa[0], text_fuer(pa[0], pa[1])), todo)
            for punkt, ergebnis in ergebnisse:
                if not ergebnis:
                    continue          # kein Text ist besser als ein erfundener
                text, quelle = ergebnis
                store.save_social_text(punkt["ksinr"], punkt["item_number"], text, quelle)
                geschrieben += 1
        return len(todo), geschrieben
    finally:
        store.close()


def probe(db_path: Path, anzahl: int, tage: int, mindest_wichtig: int) -> None:
    """Zeigen, was herauskäme — ohne zu speichern. Für Prompt-Arbeit."""
    store = CouncilStore(db_path)
    try:
        for punkt, anlagen in _mit_anlagen(store, store.agenda_items_needing_social_text(
                anzahl, tage_voraus=tage, mindest_wichtig=mindest_wichtig)):
            _dringlichkeit_nachladen(punkt)
            ktx, quelle = kontext(punkt, anlagen)
            ergebnis = text_fuer(punkt, anlagen)
            print("=" * 78)
            print(f"{punkt['committee']} · {punkt['item_number']} · "
                  f"Tragweite {punkt.get('impact')}")
            print(f"TITEL  : {(punkt['title'] or '')[:150]}")
            print(f"QUELLE : {quelle}, {len(ktx)} Zeichen, {len(anlagen)} Anlagen")
            print(f"TEXT   : {ergebnis[0] if ergebnis else '— (kein Text)'}")
    finally:
        store.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Kartentexte für Social Media (LLM)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tage", type=int, default=21, help="Vorlauf in Tagen (Default 21)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--mindest-wichtig", type=int, default=40,
                    help="Nur Punkte ab dieser Tragweite (Default 40)")
    ap.add_argument("--probe", type=int, metavar="N",
                    help="N Punkte zeigen, NICHTS speichern")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    if args.probe:
        probe(Path(args.db), args.probe, args.tage, args.mindest_wichtig)
        return 0

    todo, geschrieben = process(Path(args.db), args.limit, args.tage,
                                args.workers, args.mindest_wichtig)
    print(f"Social-Kartentexte: {geschrieben}/{todo} Punkte geschrieben", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
