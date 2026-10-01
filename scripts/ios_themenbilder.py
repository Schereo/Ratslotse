#!/usr/bin/env python3
"""Die Themen- und Gremienbilder in den Asset-Katalog der iOS-App legen.

Quelle sind die Dateien des Webs (``web/frontend/public/themen`` und
``…/gremien``, erzeugt von ``scripts/themen_grafiken.py``); Ziel ist je Bild ein
Imageset in ``ios/Resources/Assets.xcassets``:

    ThemeCycling.imageset      ← public/themen/cycling.webp
    CommitteeCouncil.imageset  ← public/gremien/council.webp

Asset-Kataloge nehmen kein WebP, deshalb PNG (192 px: die Bilder stehen mit
52 pt in der App, das trägt die dreifache Pixeldichte). Wer ein Bild neu
erzeugt, ruft das Skript danach noch einmal auf; ``--pruefen`` meldet, ob
Katalog und Web auseinanderlaufen, und schreibt nichts.

    .venv/bin/python scripts/ios_themenbilder.py             # schreiben
    .venv/bin/python scripts/ios_themenbilder.py --pruefen   # nur vergleichen
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "web" / "frontend" / "public"
KATALOG = ROOT / "ios" / "Resources" / "Assets.xcassets"
KANTE = 192

SAETZE = (("themen", "Theme"), ("gremien", "Committee"))


def asset_name(praefix: str, key: str) -> str:
    """``cycling`` → ``ThemeCycling``: derselbe Name steht in den Swift-Quellen."""
    return praefix + key[:1].upper() + key[1:]


def _png(quelle: Path) -> bytes:
    from PIL import Image

    bild = Image.open(quelle).convert("RGB").resize((KANTE, KANTE), Image.Resampling.LANCZOS)
    puffer = io.BytesIO()
    bild.save(puffer, "PNG", optimize=True)
    return puffer.getvalue()


def _contents(datei: str) -> str:
    return json.dumps({
        "images": [
            {"filename": datei, "idiom": "universal", "scale": "1x"},
            {"idiom": "universal", "scale": "2x"},
            {"idiom": "universal", "scale": "3x"},
        ],
        "info": {"author": "xcode", "version": 1},
    }, indent=2, ensure_ascii=False) + "\n"


def quellen() -> dict[str, Path]:
    """Asset-Name → Quelldatei, für alle vorhandenen Webbilder."""
    out: dict[str, Path] = {}
    for ordner, praefix in SAETZE:
        for datei in sorted((PUBLIC / ordner).glob("*.webp")):
            out[asset_name(praefix, datei.stem)] = datei
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pruefen", action="store_true", help="nur vergleichen, nichts schreiben")
    args = ap.parse_args()

    soll = quellen()
    fehlen = [n for n in soll if not (KATALOG / f"{n}.imageset" / f"{n}.png").exists()]
    if args.pruefen:
        if fehlen:
            print("Im Katalog fehlen:", ", ".join(fehlen))
            print("Abhilfe: .venv/bin/python scripts/ios_themenbilder.py")
            return 1
        print(f"{len(soll)} Bilder im Katalog.")
        return 0

    for name, quelle in soll.items():
        ziel = KATALOG / f"{name}.imageset"
        ziel.mkdir(parents=True, exist_ok=True)
        (ziel / f"{name}.png").write_bytes(_png(quelle))
        (ziel / "Contents.json").write_text(_contents(f"{name}.png"))
    print(f"{len(soll)} Imagesets geschrieben ({len(fehlen)} neu).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
