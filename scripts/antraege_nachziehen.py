#!/usr/bin/env python3
"""Anlagen an Vorlagen gegen die neue Antragserkennung halten.

Bis 11/2026 erkannte ``vorlagen._ANTRAG_LABEL_RE`` keine Komposita: Alle
Änderungs-, Berichts- und Dringlichkeitsanträge an Vorlagen standen auf
``is_motion = 0`` und bekamen nie ihren Text. Der tägliche Anlagen-Rescan
stuft nichts neu ein (bekannte ``document_id``s bleiben, wie sie sind) —
dieses Skript holt das für den Bestand nach (docs/plan-vorlagen-aufbereiten.md,
PR 2).

Standard ist der Bericht. ``--schreiben`` stuft hoch und holt fehlende Texte
nach (höchstens ``--limit`` PDFs, eines je Sekunde).

    .venv/bin/python scripts/antraege_nachziehen.py [--db data/council.sqlite]
    .venv/bin/python scripts/antraege_nachziehen.py --schreiben --limit 200
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council import anlagentext, vorlagen  # noqa: E402
from council.parties import parties_in_text  # noqa: E402
from council.store import CouncilStore  # noqa: E402

# Was die neue Erkennung NIE erfassen darf: Anträge Dritter auf Geld oder eine
# Genehmigung, die die Präfixliste bewusst auslässt. Steht so ein Label im
# Bericht, ist die Präfixliste zu weit geraten.
_DRITTE_RE = re.compile(r"(?:zuschuss|förder|genehmigungs)antr[aä]g|anlage\s*\d*antr[aä]g", re.IGNORECASE)


def main(db: str | None = None, schreiben: bool = False, limit: int = 200) -> dict:
    store = CouncilStore(db or str(ROOT / "data" / "council.sqlite"))
    kandidaten = []
    for a in store.anlagen_zur_neueinstufung():
        if vorlagen.ist_antrag(a["label"], a["kopf"]):
            ueber = "Label" if vorlagen.ist_antrag(a["label"]) else "Textkopf"
            kandidaten.append({**a, "ueber": ueber})
    dritte = [k for k in kandidaten if _DRITTE_RE.search(k["label"] or "")]
    print(f"{len(kandidaten)} Anlagen werden zum Antrag "
          f"({sum(k['ueber'] == 'Label' for k in kandidaten)} über das Label, "
          f"{sum(k['ueber'] == 'Textkopf' for k in kandidaten)} über den Textkopf).")
    for k in kandidaten[:40]:
        print(f"  {k['kvonr']:>6} {k['ueber']:<8} {k['label']}")
    if len(kandidaten) > 40:
        print(f"  … und {len(kandidaten) - 40} weitere")
    print(f"Anträge Dritter darunter (muss 0 sein): {len(dritte)}")
    for k in dritte:
        print(f"  !! {k['label']}")

    hochgestuft = gelesen = fehler = 0
    if schreiben:
        for k in kandidaten:
            text = None
            if k["status"] in ("listed", "failed") and gelesen + fehler < limit:
                try:
                    text, n_pages = vorlagen._pdf_text(k["url"], anlagentext.extraktor_fuer(k["label"]))  # noqa: SLF001
                    gelesen += 1
                    time.sleep(1)
                except Exception as exc:  # noqa: BLE001 — ein PDF kippt nicht den Lauf
                    fehler += 1
                    print(f"  {k['document_id']}: {exc!r}")
            kopf = text if text is not None else k["kopf"]
            antragsteller = parties_in_text(k["label"]) or parties_in_text((kopf or "")[:4000])
            if text is not None:
                store.anlage_als_antrag(k["document_id"], antragsteller, raw_text=text, n_pages=n_pages,
                                        status="ok" if len(text.strip()) >= 50 else "empty")
            else:
                store.anlage_als_antrag(k["document_id"], antragsteller)
            hochgestuft += 1
        print(f"Hochgestuft: {hochgestuft}, Texte geholt: {gelesen}, Fehler: {fehler}")
    store.close()
    return {"kandidaten": len(kandidaten), "dritte": len(dritte), "hochgestuft": hochgestuft,
            "gelesen": gelesen, "fehler": fehler}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db")
    ap.add_argument("--schreiben", action="store_true")
    ap.add_argument("--limit", type=int, default=200)
    a = ap.parse_args()
    main(a.db, a.schreiben, a.limit)
