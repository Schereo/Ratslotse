#!/usr/bin/env python3
"""Die Themen- und Gremienbilder in den Asset-Katalog der iOS-App legen.

Quelle sind die Dateien des Webs (``web/frontend/public/themen`` und
``…/gremien``, erzeugt von ``scripts/themen_grafiken.py``); Ziel ist je Bild ein
Imageset in ``ios/Resources/Assets.xcassets``:

    ThemeCycling.imageset      ← public/themen/cycling.webp
    CommitteeCouncil.imageset  ← public/gremien/council.webp

Asset-Kataloge nehmen kein WebP, deshalb PNG. Die Kante hängt am Satz: Themen
stehen mit 52 pt in der App (192 px trägt die dreifache Pixeldichte), Gremien
seit 11/2026 mit 72 pt und leicht herangezoomt, dafür die volle Quelle mit
256 px. Wer ein Bild neu
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
#: (Ordner unter ``public``, Präfix im Katalog, Kantenlänge in px)
SAETZE = (("themen", "Theme", 192), ("gremien", "Committee", 256))


def asset_name(praefix: str, key: str) -> str:
    """``cycling`` → ``ThemeCycling``: derselbe Name steht in den Swift-Quellen."""
    return praefix + key[:1].upper() + key[1:]


def _png(quelle: Path, kante: int) -> bytes:
    from PIL import Image

    bild = Image.open(quelle).convert("RGB").resize((kante, kante), Image.Resampling.LANCZOS)
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


def quellen() -> dict[str, tuple[Path, int]]:
    """Asset-Name → (Quelldatei, Kantenlänge), für alle vorhandenen Webbilder."""
    out: dict[str, tuple[Path, int]] = {}
    for ordner, praefix, kante in SAETZE:
        for datei in sorted((PUBLIC / ordner).glob("*.webp")):
            out[asset_name(praefix, datei.stem)] = (datei, kante)
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

    for name, (quelle, kante) in soll.items():
        ziel = KATALOG / f"{name}.imageset"
        ziel.mkdir(parents=True, exist_ok=True)
        (ziel / f"{name}.png").write_bytes(_png(quelle, kante))
        (ziel / "Contents.json").write_text(_contents(f"{name}.png"))
    print(f"{len(soll)} Imagesets geschrieben ({len(fehlen)} neu).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
