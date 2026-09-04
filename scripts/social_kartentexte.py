#!/usr/bin/env python3
"""Kartentexte für Social Media schreiben — ein Satz je Tagesordnungspunkt.

Der dritte Text neben Kurzfassung und Tragweite-Grund, und der einzige, der
die **ganze Vorlage samt Anlagen** sieht. Warum das nötig ist, steht in
``council/social_text.py``; kurz: Die Kurzfassung kennt nur den Titel, der
Tragweite-Grund wertet (er begründet eine Rangfolge).

Läuft täglich HINTER ``rate_agenda_impact.py``. Geschrieben wird für **jeden
inhaltlichen Punkt** der nächsten drei Wochen, nicht mehr nur für die rund 20
von 97, die auf eine Instagram-Karte kommen: Im Web wird die Tagesordnung
ganz gelesen, und unter den übrigen stand bis dahin die titelbasierte
Kurzfassung oder gar nichts (Tims Entscheidung 30.08.26). Die Tragweite
entscheidet seitdem nur noch die Reihenfolge — wer hoch steht, kommt zuerst
dran. Formalien bleiben draußen::

    python scripts/social_kartentexte.py --limit 40
    python scripts/social_kartentexte.py --probe 5      # nur zeigen, nichts speichern

Bereits Geschriebenes wird nie erneut bezahlt (Tabelle
``agenda_item_social``, Schlüssel ksinr + item_number).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council.social_text import (  # noqa: E402
    _dringlichkeit_nachladen, _mit_anlagen, kontext, schreibe_fehlende, text_fuer,
)
from council.store import CouncilStore  # noqa: E402
from kern.alerts import run_guarded  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")


def process(db_path: Path, limit: int | None, tage: int, workers: int,
            mindest_wichtig: int) -> tuple[int, int]:
    """Der Nachtlauf. Die Arbeit selbst steht in ``social_text``, weil die
    Tagesordnungs-Mail dieselbe braucht — nur für eine einzelne Sitzung und
    sofort (``schreibe_fehlende(..., ksinr=…)``)."""
    store = CouncilStore(db_path)
    try:
        return schreibe_fehlende(store, limit=limit, tage_voraus=tage,
                                 mindest_wichtig=mindest_wichtig, workers=workers)
    finally:
        store.close()


def probe(db_path: Path, count: int, tage: int, mindest_wichtig: int) -> None:
    """Zeigen, was herauskäme — ohne zu speichern. Für Prompt-Arbeit."""
    store = CouncilStore(db_path)
    try:
        for punkt, anlagen in _mit_anlagen(store, store.agenda_items_needing_social_text(
                count, tage_voraus=tage, mindest_wichtig=mindest_wichtig)):
            _dringlichkeit_nachladen(punkt)
            ktx, source = kontext(punkt, anlagen)
            result = text_fuer(punkt, anlagen)
            print("=" * 78)
            print(f"{punkt['committee']} · {punkt['item_number']} · "
                  f"Tragweite {punkt.get('impact')}")
            print(f"TITEL  : {(punkt['title'] or '')[:150]}")
            print(f"QUELLE : {source}, {len(ktx)} Zeichen, {len(anlagen)} Anlagen")
            print(f"TEXT   : {result[0] if result else '— (kein Text)'}")
    finally:
        store.close()


def main() -> dict:
    """Ein dict, kein Exit-Code: ``run_guarded`` speichert es als Kennzahlen
    des Laufs (``kern/alerts.py``). Wer hier ``int`` zurückgibt, bekommt einen
    ``job_runs``-Eintrag ohne jede Zahl — geprüft wird das nicht."""
    ap = argparse.ArgumentParser(description="Kartentexte für Social Media (LLM)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tage", type=int, default=21, help="Vorlauf in Tagen (Default 21)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--mindest-wichtig", type=int, default=0,
                    help="Nur Punkte ab dieser Tragweite (Default 0 = alle "
                         "inhaltlichen; Formalien bleiben immer draußen)")
    ap.add_argument("--probe", type=int, metavar="N",
                    help="N Punkte zeigen, NICHTS speichern")
    ap.add_argument("--db", default=str(COUNCIL_DB))
    args = ap.parse_args()

    if args.probe:
        probe(Path(args.db), args.probe, args.tage, args.mindest_wichtig)
        return {"Probe": args.probe}

    todo, geschrieben = process(Path(args.db), args.limit, args.tage,
                                args.workers, args.mindest_wichtig)
    print(f"Social-Kartentexte: {geschrieben}/{todo} Punkte geschrieben", flush=True)
    return {"Punkte geschrieben": geschrieben, "Punkte offen": max(todo - geschrieben, 0)}


if __name__ == "__main__":
    # **Warum das hier steht.** Bis 09/2026 lief dieses Skript als einziger
    # Cron auf Prod OHNE `run_guarded` — täglich um 7:45, mit LLM-Kosten, und
    # damit doppelt blind: kein `job_runs`-Eintrag (also nichts im Admin-Panel)
    # und keine Alarmmail beim Absturz. Aufgefallen ist es erst beim
    # Nachzählen am 04.09.2026, weil `kern/jobs.py` es auch nicht kannte.
    raise SystemExit(run_guarded("social_kartentexte", main))
