#!/usr/bin/env python3
"""Das Ergebnis „gilt als behandelt" im Bestand nachziehen.

Bis 09/2026 stand die amtliche Formel „gilt als behandelt" verstreut auf
``no_decision``, ``accepted``, ``postponed`` und ``noted`` — das Modell hörte
das „einstimmig" des Verfahrensantrags und nahm den Inhalt für angenommen
(Datensatz 19018, Schlossplatz-Spielplatz: „Frag den Rat" zitierte ihn als
Auftrag, Mittel in den Haushalt einzustellen). Seit ``settled`` gilt eine
feste Regel (``council.votes.normalize_outcome``), die schon beim Einlesen
greift; dieses Skript wendet sie auf den Bestand an.

Nur Hauptpunkte (``kind='decision'``), und der Original-Abstimmungssatz
(``raw_result``) entscheidet. Ein Verfahrensantrag selbst (``subvote``) wird ja
tatsächlich angenommen oder abgelehnt und bleibt, wie er ist.

Jede Änderung steht als Zeile im Bericht (``id  alt → neu  Satz``): Wer es
zurückdrehen will, hat die Liste. Ein zweiter Lauf findet nichts mehr.

Danach ``scripts/fix_outcome_summaries.py --schreiben``: Die Kurzfassungen der
umgestellten Zeilen sprachen vom Vorschlag als beschlossen und werden neu
geschrieben (das Ergebnis steht jetzt im Prompt).

    python scripts/fix_settled_outcomes.py               # Bericht
    python scripts/fix_settled_outcomes.py --schreiben   # umschreiben
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.store import CouncilStore  # noqa: E402
from council.votes import normalize_outcome  # noqa: E402

COUNCIL_DB = ROOT / "data" / "council.sqlite"


def plan(store: CouncilStore) -> list[tuple[int, str | None, str | None, str]]:
    """``[(id, alt, neu, raw_result)]`` für alle Hauptpunkte, die sich ändern."""
    aenderungen = []
    rows = store._conn.execute(
        "SELECT id, outcome, raw_result FROM council_decisions WHERE kind = 'decision'"
    ).fetchall()
    for id_, alt, raw in rows:
        neu = normalize_outcome(alt, raw, "decision")
        if neu != alt:
            aenderungen.append((id_, alt, neu, raw or ""))
    return aenderungen


def main() -> dict:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=COUNCIL_DB)
    ap.add_argument("--schreiben", action="store_true", help="wirklich schreiben (sonst nur Bericht)")
    args = ap.parse_args()
    store = CouncilStore(args.db)
    try:
        aenderungen = plan(store)
        for id_, alt, neu, raw in sorted(aenderungen, key=lambda a: (a[2] or "", a[0])):
            print(f"{id_:>6}  {alt or '-':>11} → {neu:<9}  {re.sub(r'\s+', ' ', raw)[:110]}")
        uebergang = Counter((alt, neu) for _, alt, neu, _ in aenderungen)
        print("\nÜbergänge:", {f"{a} → {n}": k for (a, n), k in sorted(uebergang.items(), key=str)})
        if args.schreiben and aenderungen:
            with store._conn:
                store._conn.executemany(
                    "UPDATE council_decisions SET outcome = ? WHERE id = ? AND kind = 'decision'",
                    [(neu, id_) for id_, _, neu, _ in aenderungen])
            print(f"{len(aenderungen)} Hauptpunkte umgestellt.")
        elif aenderungen:
            print(f"{len(aenderungen)} würden umgestellt (Bericht — mit --schreiben ausführen).")
        else:
            print("Nichts zu tun.")
        return {"umgestellt": len(aenderungen) if args.schreiben else 0,
                "faellig": len(aenderungen)}
    finally:
        store.close()


if __name__ == "__main__":
    main()
