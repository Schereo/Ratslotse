#!/usr/bin/env python3
"""Erzeugt ``web/frontend/lib/glossary.ts`` aus ``kern/glossar.py``.

Die Erklärungen brauchen beide Seiten: das Backend für den Prompt der KI-Frage,
das Frontend für die Tooltips im Antworttext. Zwei handgepflegte Listen wären
nach dem zweiten Begriff auseinandergelaufen — und zwar lautlos, weil nichts
scheitert, wenn eine Seite ein Wort nicht kennt: Der Tooltip fehlt, das Modell
rät, niemand merkt es.

Deshalb ist Python die Quelle und die TypeScript-Datei erzeugt, nach dem Muster
der API-Typen: Am Dateiende steht eine SHA-256-Zeile über die Quelle, die
``scripts/pruefe.py`` (Prüfung „glossar") ohne Node nachrechnet.

    python scripts/glossar_ts.py            # schreiben
    python scripts/glossar_ts.py --pruefen  # nur melden, ob es passt
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from kern import glossar  # noqa: E402

ZIEL = WURZEL / "web" / "frontend" / "lib" / "glossary.ts"
QUELLE = WURZEL / "kern" / "glossar.py"

KOPF = """\
/** ERZEUGTE DATEI — NICHT VON HAND ÄNDERN.
 *
 *  Quelle ist `kern/glossar.py`; neu erzeugen mit
 *  `python scripts/glossar_ts.py`. Die Erklärungen liegen dort, weil die
 *  KI-Frage sie im Prompt braucht: Das Modell antwortet nur aus dem, was im
 *  Prompt steht, und eine reine Frontend-Liste erreicht es nie.
 *
 *  Schlüssel = Grundform des Begriffs; gematcht wird ab Wortanfang mit
 *  beliebiger Buchstaben-Endung (`components/glossary-text.tsx`), sodass
 *  Beugungen wie „Bebauungsplans" oder „Vergnügungsstätten" mitgefunden
 *  werden. Ein Kompositum, das den Begriff hinten trägt, braucht einen
 *  eigenen Eintrag.
 */
export const GLOSSARY: Record<string, string> = {
"""


def _ts_string(s: str) -> str:
    """Ein TypeScript-String in doppelten Anführungszeichen.

    Die Erklärungen benutzen deutsche Anführungszeichen („…"), gerade
    Anführungszeichen kämen also normalerweise nicht vor — maskiert werden sie
    trotzdem, sonst risse ein einziger Tippfehler später den Frontend-Build.
    """
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def erzeuge() -> str:
    zeilen = [KOPF]
    for begriff, erklaerung in glossar.BEGRIFFE.items():
        zeilen.append(f"  {_ts_string(begriff)}:\n    {_ts_string(erklaerung)},\n")
    zeilen.append("};\n")
    summe = hashlib.sha256(QUELLE.read_bytes()).hexdigest()
    zeilen.append(f"\n// glossar-sha256: {summe}\n")
    return "".join(zeilen)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pruefen", action="store_true",
                   help="nichts schreiben, nur melden, ob die Datei aktuell ist")
    args = p.parse_args()

    neu = erzeuge()
    alt = ZIEL.read_text(encoding="utf-8") if ZIEL.exists() else None
    if args.pruefen:
        if alt == neu:
            print(f"lib/glossary.ts passt zu kern/glossar.py ({len(glossar.BEGRIFFE)} Begriffe).")
            return 0
        print("web/frontend/lib/glossary.ts ist nicht auf dem Stand von kern/glossar.py.\n"
              "  python scripts/glossar_ts.py", file=sys.stderr)
        return 1
    if alt == neu:
        print(f"lib/glossary.ts war schon aktuell ({len(glossar.BEGRIFFE)} Begriffe).")
        return 0
    ZIEL.write_text(neu, encoding="utf-8")
    print(f"lib/glossary.ts neu geschrieben ({len(glossar.BEGRIFFE)} Begriffe).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
