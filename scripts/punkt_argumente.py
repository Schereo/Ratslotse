#!/usr/bin/env python3
"""Argumente zu Tagesordnungspunkten erzeugen — der Bestand für die Punkt-Seite.

Plan: ``docs/plan-punkt-argumente.md``. Ein Modellaufruf je Vorgang (Vorlage,
sonst datierter Antragstitel), nicht je Punkt: Eine Auswertung gilt für alle
Stationen eines Vorgangs. Neu gerechnet wird nur, wo seit dem letzten Lauf
Wortbeiträge dazugekommen sind (``sources_hash``).

**Ohne ``--schreiben`` nur Bericht**: wie viele Vorgänge Stoff haben, wie
viele schon ausgewertet sind und was ein Lauf ungefähr kostet (gemessen
11/2026: 0,0006 $ je Vorgang mit GPT-6 Luna im Flex-Tarif).

    python scripts/punkt_argumente.py                       # Bericht, letzte 12 Monate
    python scripts/punkt_argumente.py --seit 2024-01-01     # Bericht ab Datum
    python scripts/punkt_argumente.py --schreiben --limit 20
    python scripts/punkt_argumente.py --schreiben --max-usd 1

Gemessen wurde die Güte an 20 Punkten (``eval/run_punkt_argumente.py``,
Urteile in ``eval/punkt_argumente_gold.json``).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from council import arguments  # noqa: E402
from council.store import CouncilStore  # noqa: E402
from kern import llm  # noqa: E402

COUNCIL_DB = Path(os.environ.get("COUNCIL_DB") or ROOT / "data" / "council.sqlite")
#: Unter so vielen Wortbeiträgen kommen keine zwei Seiten mit je zwei Aussagen
#: zusammen — der Aufruf wäre bezahlt und der Reiter trotzdem leer.
MIN_BEITRAEGE = 4
#: Gemessen am 10.11.2026 über 20 Vorgänge (0,0116 $), aufgerundet.
USD_JE_VORGANG = 0.0008


def kandidaten(store: CouncilStore, seit: str) -> list[dict]:
    """Je Vorgang der jüngste öffentliche Punkt seit ``seit`` mit genug Stoff."""
    rows = store.public_agenda_items_since(seit)
    gesehen: set[str] = set()
    out = []
    for r in rows:
        m = store.item_argument_material(r["ksinr"], r["item_number"])
        if not m or m["subject_key"] in gesehen:
            continue
        gesehen.add(m["subject_key"])
        if len(m["speeches"]) < MIN_BEITRAEGE:
            continue
        m["hash"] = arguments.sources_hash([s["id"] for s in m["speeches"]], m["template_number"])
        alt = store.item_arguments(m["subject_key"])
        m["aktuell"] = bool(alt) and alt["sources_hash"] == m["hash"]
        out.append(m)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--db", default=str(COUNCIL_DB))
    ap.add_argument("--seit", default=(date.today() - timedelta(days=365)).isoformat(),
                    help="Sitzungen ab diesem Datum (Vorgabe: ein Jahr zurück)")
    ap.add_argument("--limit", type=int, default=0, help="höchstens so viele Vorgänge auswerten")
    ap.add_argument("--max-usd", type=float, default=1.0, help="Kostengrenze für den Lauf (Vorgabe 1 $)")
    ap.add_argument("--schreiben", action="store_true", help="wirklich auswerten und speichern")
    a = ap.parse_args()

    store = CouncilStore(a.db)
    alle = kandidaten(store, a.seit)
    offen = [m for m in alle if not m["aktuell"]]
    if a.limit:
        offen = offen[:a.limit]
    print(f"{len(alle)} Vorgänge mit Stoff seit {a.seit}, davon {len(alle) - len([m for m in alle if not m['aktuell']])} "
          f"aktuell ausgewertet; dieser Lauf: {len(offen)} · geschätzt {len(offen) * USD_JE_VORGANG:.2f} $")
    if not a.schreiben:
        print("Bericht — mit --schreiben auswerten.")
        return 0

    start = llm.session_cost()["usd"]
    fertig = leer = fehler = 0
    for m in offen:
        if llm.session_cost()["usd"] - start >= a.max_usd:
            print(f"Kostengrenze {a.max_usd} $ erreicht — Rest beim nächsten Lauf.")
            break
        try:
            payload = arguments.generate(m["title"], m["speeches"], m["template"], m["outcome_note"])
        except Exception as e:  # noqa: BLE001 — ein Vorgang, nicht der Lauf
            fehler += 1
            print(f"  ! {m['subject_key']}: {type(e).__name__}: {e}")
            continue
        if payload is None:
            fehler += 1
            continue
        # Auch ein leeres Ergebnis wird gespeichert: Es heißt „kein Streit“,
        # und der nächste Lauf fragt erst wieder, wenn Beiträge dazukommen.
        store.save_item_arguments(m["subject_key"], m["hash"], arguments.MODEL, payload)
        fertig += 1
        leer += int(not arguments.zeigen(payload))
    usd = llm.session_cost()["usd"] - start
    print(f"{fertig} ausgewertet ({leer} ohne genug Streit für den Reiter), {fehler} Fehler · {usd:.4f} $")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
