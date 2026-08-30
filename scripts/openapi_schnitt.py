#!/usr/bin/env python3
"""Schreibt das OpenAPI-Schema der API nach ``api/openapi.json``.

**Wozu.** Die Datei ist der eingecheckte Vertrag zwischen Backend und den
beiden Frontends (Web und iOS). Zwei Dinge fallen dadurch ab:

1. **Schnittstellenänderungen stehen im PR-Diff.** Wer ein Feld umbenennt,
   sieht es beim Review — und merkt, dass die App das auch braucht. Ohne die
   Datei fällt so etwas erst auf, wenn ein Client nichts mehr anzeigt.
2. **Beide Clients können daraus generieren** statt Typen abzuschreiben:
   ``openapi-typescript`` fürs Web, ``swift-openapi-generator`` für iOS.

Aufruf::

    python scripts/openapi_schnitt.py            # schreibt api/openapi.json
    python scripts/openapi_schnitt.py --pruefen  # nur vergleichen (CI, Exit 1)

Das Schema hängt an keiner Datenbank — die Endpunkte werden nur eingelesen,
nicht aufgerufen. ``WEB_JWT_SECRET`` wird gesetzt, weil die Konfiguration es
beim Import verlangt; ein Wert aus der Umgebung hätte hier keine Wirkung.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
ZIEL = WURZEL / "api" / "openapi.json"


def schema() -> dict:
    sys.path.insert(0, str(WURZEL / "web" / "backend"))
    os.environ.setdefault("WEB_JWT_SECRET", "schema-export")
    from app.main import app

    return app.openapi()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pruefen", action="store_true",
                   help="nicht schreiben, nur vergleichen (für die CI)")
    args = p.parse_args()

    text = json.dumps(schema(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    if args.pruefen:
        if not ZIEL.exists():
            print(f"FEHLT: {ZIEL.relative_to(WURZEL)} — einmal ohne --pruefen laufen lassen.")
            return 1
        if ZIEL.read_text() != text:
            print(f"VERALTET: {ZIEL.relative_to(WURZEL)} passt nicht zum Code.\n"
                  f"  python scripts/openapi_schnitt.py   # neu erzeugen und mitcommitten")
            return 1
        print(f"{ZIEL.relative_to(WURZEL)} ist aktuell.")
        return 0

    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    vorher = ZIEL.read_text() if ZIEL.exists() else None
    ZIEL.write_text(text)
    print(f"{'unverändert' if vorher == text else 'geschrieben'}: {ZIEL.relative_to(WURZEL)} "
          f"({len(schema()['paths'])} Pfade)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
