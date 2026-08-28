"""Mail-Helden bauen: 3D-Lotti-Renders → fertige E-Mail-Banner.

Die Szenen (``szenen/mail-*.json``) beschreiben die 3D-Posen deklarativ; das
Lotti-Studio im Repo ``ratslotse-social`` rendert sie headless zu Alpha-PNGs
(Modell und Licht kommen von dort, damit die Mail-Lotti exakt wie jede andere
Lotti aussieht). Dieses Skript kopiert die Szenen ins Studio, rendert und setzt
jede Figur auf ihre Bühne: Himmel-Verlauf, zwei Hafenblau-Wellen, gerundete
obere Ecken — das Ergebnis landet als ``web/frontend/public/mail/held-*.png``
(600×210 CSS-px, geliefert in 2×) und wird von den E-Mails über
``APP_BASE_URL`` referenziert.

Läuft nur auf einem Rechner mit dem Studio-Checkout — die fertigen Banner sind
eingecheckt, der Server braucht dieses Skript nie.

    .venv/bin/python scripts/mail_helden/bauen.py             # nur komponieren
    .venv/bin/python scripts/mail_helden/bauen.py --rendern   # erst 3D rendern
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HIER = Path(__file__).resolve().parent
REPO = HIER.parent.parent
SZENEN = HIER / "szenen"
ZIEL = REPO / "web" / "frontend" / "public" / "mail"

# Der Studio-Checkout (privates Repo ratslotse-social) — nur zum Rendern nötig.
STUDIO = Path(os.environ.get("LOTTI_STUDIO", Path.home() / "Documents" / "ratslotse-social" / "studio"))

# Banner: 600×210 CSS-px, gebaut in 2× für scharfe Retina-Darstellung.
BREITE, HOEHE = 1200, 420
ECKRADIUS = 36  # 2× der 18px-Kartenrundung der Mail-Hülle

# Bühne: Himmel oben hell, unten einen Hauch satter — bewusst nah an der
# Seitenfarbe der App (hsl 204 45% 97.5%), damit Mail und App zusammengehören.
HIMMEL_OBEN = (242, 248, 252)
HIMMEL_UNTEN = (219, 234, 245)
HAFENBLAU = (7, 100, 166)  # #0764a6, --primary

# Je Held: Anteil der Bannerhöhe, den die Figur einnimmt, und Feinversatz
# (x als Anteil der Breite relativ zur Mitte, y in Pixeln von der Unterkante).
HELDEN: dict[str, dict] = {
    "willkommen":     {"anteil": 0.86},
    "meldung":        {"anteil": 0.88},
    "passwort":       {"anteil": 0.90},
    "freigeschaltet": {"anteil": 0.94},
    "abschied":       {"anteil": 0.88},
    "erinnerung":     {"anteil": 0.90},
    "feedback":       {"anteil": 0.86},
    "alarm":          {"anteil": 0.86},
}


def rendern() -> None:
    """Szenen ins Studio kopieren, headless rendern, Kopien wieder entfernen —
    die Quelle der Wahrheit bleibt dieses Repo."""
    kopien = []
    for szene in sorted(SZENEN.glob("mail-*.json")):
        kopie = STUDIO / "szenen" / szene.name
        shutil.copy(szene, kopie)
        kopien.append(kopie)
    try:
        subprocess.run(
            ["node", str(STUDIO / "render.mjs"), *[k.stem for k in kopien]],
            cwd=STUDIO.parent, check=True,
        )
    finally:
        for kopie in kopien:
            kopie.unlink(missing_ok=True)


def _buehne() -> Image.Image:
    """Verlauf plus zwei ruhige Wellenbänder am Fuß."""
    bild = Image.new("RGB", (BREITE, HOEHE))
    for y in range(HOEHE):
        t = y / (HOEHE - 1)
        farbe = tuple(round(o + (u - o) * t) for o, u in zip(HIMMEL_OBEN, HIMMEL_UNTEN))
        bild.paste(farbe, (0, y, BREITE, y + 1))

    ebene = Image.new("RGBA", (BREITE, HOEHE), (0, 0, 0, 0))
    zeichner = ImageDraw.Draw(ebene)
    # (Grundlinie von unten, Amplitude, Wellenlänge, Phase, Deckkraft)
    for grund, amp, laenge, phase, alpha in ((96, 14, 560, 0.0, 22), (52, 18, 430, 2.1, 34)):
        punkte = [(x, HOEHE - grund + amp * math.sin(2 * math.pi * x / laenge + phase))
                  for x in range(0, BREITE + 8, 8)]
        zeichner.polygon(punkte + [(BREITE, HOEHE), (0, HOEHE)], fill=(*HAFENBLAU, alpha))
    bild = Image.alpha_composite(bild.convert("RGBA"), ebene)
    return bild


def _ecken_runden(bild: Image.Image) -> Image.Image:
    """Nur die oberen Ecken — das Banner sitzt oben in der Mail-Karte,
    unten läuft die Karte weiter."""
    maske = Image.new("L", bild.size, 255)
    zeichner = ImageDraw.Draw(maske)
    zeichner.rectangle((0, 0, ECKRADIUS, ECKRADIUS), fill=0)
    zeichner.pieslice((0, 0, 2 * ECKRADIUS, 2 * ECKRADIUS), 180, 270, fill=255)
    zeichner.rectangle((BREITE - ECKRADIUS, 0, BREITE, ECKRADIUS), fill=0)
    zeichner.pieslice((BREITE - 2 * ECKRADIUS, 0, BREITE, 2 * ECKRADIUS), 270, 360, fill=255)
    bild.putalpha(maske)
    return bild


def komponieren(name: str, einstellung: dict) -> Path:
    render = STUDIO / "build" / f"mail-{name}.png"
    figur = Image.open(render).convert("RGBA")
    figur = figur.crop(figur.getbbox())

    ziel_h = HOEHE * einstellung["anteil"]
    ziel_w = BREITE * 0.66
    faktor = min(ziel_h / figur.height, ziel_w / figur.width)
    figur = figur.resize((round(figur.width * faktor), round(figur.height * faktor)),
                         Image.LANCZOS)

    banner = _buehne()
    x = round(BREITE / 2 - figur.width / 2 + einstellung.get("x", 0.0) * BREITE)
    y = HOEHE - einstellung.get("y", 26) - figur.height
    banner.alpha_composite(figur, (x, y))
    banner = _ecken_runden(banner)

    ZIEL.mkdir(parents=True, exist_ok=True)
    ziel = ZIEL / f"held-{name}.png"
    # PNG-8 mit Alphakanal: ein Viertel der Dateigröße, und der weiche Verlauf
    # übersteht die Quantisierung dank Dithering ohne sichtbare Streifen.
    klein = banner.quantize(colors=256, method=Image.Quantize.FASTOCTREE,
                            dither=Image.Dither.FLOYDSTEINBERG)
    klein.save(ziel, optimize=True)
    return ziel


def main() -> None:
    if "--rendern" in sys.argv:
        rendern()
    fehlend = [n for n in HELDEN if not (STUDIO / "build" / f"mail-{n}.png").exists()]
    if fehlend:
        sys.exit(f"Renders fehlen ({', '.join(fehlend)}) — erst mit --rendern laufen lassen.")
    for name, einstellung in HELDEN.items():
        ziel = komponieren(name, einstellung)
        print(f"{name}: {ziel.stat().st_size // 1024} KiB → {ziel.relative_to(REPO)}")


if __name__ == "__main__":
    main()
