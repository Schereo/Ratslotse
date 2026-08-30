"""Den aktuellen Lotti-Stand aus ratslotse-social ins Frontend übernehmen.

    .venv/bin/python scripts/lotti_uebernehmen.py [pfad-zum-social-repo]

Lotti wird im Repo ratslotse-social gebaut (studio/) und hier nur benutzt.
Damit „am Modell drehen" nicht heißt „das Frontend altert still", ist die
Übernahme EIN Befehl, der beide Kopien zugleich zieht:

  assets/lotti/*          → web/frontend/public/lotti/     (Sprite-Bündel:
                            Blätter, Verzeichnis, Abspieler, Standbilder)
  studio/lotti-modell.js  → web/frontend/lib/lotti/modell.js   (3D-Figur)
  studio/skelett.js       → web/frontend/lib/lotti/skelett.js  (Knochenbau)

Die Modell-Dateien sind WÖRTLICHE Kopien — keine TypeScript-Ports, keine
hiesigen Anpassungen (tsconfig hat allowJs). Wer an der Figur etwas ändern
will, ändert sie im Social-Repo und ruft danach dieses Skript; ein Diff der
Kopie gegen die Quelle muss immer leer sein.

Geprüft wird der STEMPEL, nicht das Datum: `sprites.mjs` schreibt beim
Backen Modellversion + Fingerabdruck in lotti.json. Steht in der kopierten
modell.js eine andere MODELL_VERSION als im Bündel, wurde am Modell gedreht,
ohne die Blätter neu zu backen — dann liefe die 3D-Lotti der Startseite
einer anderen Figur voraus als die Sprites. Das Skript warnt und nennt den
Backen-Befehl.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
FRONTEND = HIER / "web" / "frontend"

QUELLE_VORGABE = Path.home() / "Documents" / "ratslotse-social"

# Was aus studio/ gebraucht wird — bewusst nur die zwei Dateien, die die
# Figur selbst tragen. Render-Werkzeug, Szenen und Playwright bleiben drüben.
MODELL_DATEIEN = {
    "studio/lotti-modell.js": "lib/lotti/modell.js",
    "studio/skelett.js": "lib/lotti/skelett.js",
}


def main() -> dict:
    quelle = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else QUELLE_VORGABE
    buendel = quelle / "assets" / "lotti"
    if not (buendel / "lotti.json").is_file():
        sys.exit(
            f"Kein Lotti-Bündel unter {buendel} — liegt das Social-Repo woanders?\n"
            f"Aufruf: python scripts/lotti_uebernehmen.py <pfad-zum-social-repo>"
        )

    # ── Sprite-Bündel: Zielordner ist vollständig abgeleitet, also erst leeren —
    #    eine im Studio entfernte Regung soll hier kein Standbild zurücklassen.
    ziel = FRONTEND / "public" / "lotti"
    if ziel.exists():
        shutil.rmtree(ziel)
    shutil.copytree(buendel, ziel)
    dateien = sorted(p.name for p in ziel.iterdir())

    # ── Modell-Dateien: wörtlich kopieren.
    for von, nach in MODELL_DATEIEN.items():
        (FRONTEND / nach).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(quelle / von, FRONTEND / nach)

    # ── Stempel-Abgleich: Bündel gegen Modell.
    verzeichnis = json.loads((ziel / "lotti.json").read_text())
    stempel = verzeichnis.get("modell", "?")
    modell_js = (FRONTEND / "lib" / "lotti" / "modell.js").read_text()
    m = re.search(r"MODELL_VERSION = '([^']+)'", modell_js)
    version = m.group(1) if m else "?"
    passt = stempel.startswith(version)

    print(f"Bündel:  {len(dateien)} Dateien nach web/frontend/public/lotti/")
    print(f"Modell:  {', '.join(MODELL_DATEIEN.values())}")
    print(f"Stempel: Blätter „{stempel}“, Modell „{version}“", end=" — ")
    if passt:
        print("passt.")
    else:
        print("PASST NICHT!")
        print(
            "  Am Modell wurde gedreht, ohne die Blätter neu zu backen.\n"
            f"  Im Social-Repo:  node studio/sprites.mjs --nach assets/lotti --standbilder\n"
            "  Danach dieses Skript noch einmal."
        )
    print(f"Regungen: {len(verzeichnis.get('regungen', {}))}")
    return {"dateien": len(dateien), "stempel_passt": passt}


if __name__ == "__main__":
    main()
