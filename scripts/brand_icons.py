#!/usr/bin/env python3
"""App-Icon, Favicons, Mail-Logo und Vorschaubilder aus der 3D-Lotti setzen.

    python3 scripts/brand_icons.py                     # alle Dateien schreiben
    python3 scripts/brand_icons.py --vorschau /tmp/ic  # dazu ein Übersichtsblatt
    python3 scripts/brand_icons.py --social ~/Pfad/zu/ratslotse-social

WOHER DAS BILD KOMMT. Bis 11/2026 war die Marke ein handgezeichnetes
Flat-SVG (``components/brand.tsx``), und die Icons waren PNG-Abzüge davon —
per ``qlmanage`` und ``sips`` von Hand erzeugt, nirgends nachvollziehbar.
Die Lotti der Seite war da längst die 3D-Figur aus dem Studio; das Logo
war die einzige Stelle, an der noch die alte Zeichnung stand (Tims Wunsch
25.11.26: „überall ein Bild von der 3D-Lotti").

Jetzt entsteht alles aus EINEM Render: der Szene ``app-icon`` im Studio von
``ratslotse-social``, über ``studio/marke.py`` nach
``assets/marke/lotti-app-icon.png`` gelegt — Kopf und Mütze, transparent,
auf den sichtbaren Inhalt beschnitten. Dieses Skript setzt die Figur auf
den Hafenblau-Grund und schreibt jede Größe, die irgendwo gebraucht wird.

DIE UNTERKANTE IST EINE SCHNITTKANTE. Der Körper läuft im Render unten aus
dem Bild; die Figur wird deshalb bündig an den unteren Rand jeder Kachel
gesetzt. Säße sie höher, endete der Körper mit einer geraden Linie mitten
im Blau.

Wer die Figur ändern will, ändert die Szene drüben, rendert mit
``python3 studio/marke.py app-icon`` und lässt dieses Skript laufen. Die
Dateien hier sind Erzeugnisse, keine Quellen — bitte nicht von Hand
nachbearbeiten.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "frontend"
IOS_ASSETS = ROOT / "ios" / "Resources" / "Assets.xcassets"

#: Hafenblau, diagonal von oben links nach unten rechts — derselbe Verlauf
#: wie das alte Icon, damit die Kachel im Homescreen nicht die Farbe wechselt.
BLUE = ((11, 114, 184), (10, 61, 102))
#: Der Grund des dunklen iOS-Icons (wie bisher).
NIGHT = ((18, 40, 59), (11, 23, 35))
#: Signal-Orange der Designsprache.
SIGNAL = (246, 102, 35)

#: Breite der Figur im Verhältnis zur Kachel. Die Mützenkrempe ist das
#: Breiteste; bei 0,84 bleibt sie in der iOS-Squircle-Maske frei.
FULL = 0.84
#: Für „maskable" (Android schneidet bis auf einen Kreis mit 80 % Durchmesser
#: zu): Mütze und Gesicht müssen in diesen Kreis passen.
MASKABLE = 0.66
#: Eckenradius der eingebrannten Rundung, wie iOS (≈ 22,4 % der Kante).
CORNER = 0.2237


def _find_social(given: str | None) -> Path:
    """Den Checkout von ratslotse-social finden: Argument, Umgebung, dann
    neben diesem Repo."""
    for candidate in (given, os.environ.get("RATSLOTSE_SOCIAL")):
        if candidate:
            path = Path(candidate).expanduser()
            if (path / "studio" / "marke.py").exists():
                return path
            sys.exit(f"ratslotse-social nicht gefunden unter {path}")
    for parent in ROOT.parents:
        path = parent / "ratslotse-social"
        if (path / "studio" / "marke.py").exists():
            return path
    sys.exit("ratslotse-social nicht gefunden — --social PFAD oder RATSLOTSE_SOCIAL setzen")


def _load(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGBA")
    box = image.getchannel("A").getbbox()
    return image.crop(box) if box else image


def _gradient(width: int, height: int, colors: tuple[tuple[int, int, int], ...],
              diagonal: bool = True) -> Image.Image:
    """Linearer Verlauf ohne numpy: Bei ``diagonal`` ist der Anteil
    (x + y) / 2, also der Mittelwert eines waagerechten und eines
    senkrechten Verlaufs."""
    vertical = Image.linear_gradient("L").resize((width, height))
    if diagonal:
        # linear_gradient läuft von oben (0) nach unten (255); um 90° gegen
        # den Uhrzeigersinn gedreht, von links nach rechts.
        horizontal = Image.linear_gradient("L").rotate(90).resize((width, height))
        mask = Image.blend(vertical, horizontal, 0.5)
    else:
        mask = vertical
    top = Image.new("RGBA", (width, height), (*colors[0], 255))
    bottom = Image.new("RGBA", (width, height), (*colors[1], 255))
    return Image.composite(bottom, top, mask)


def _scaled(figure: Image.Image, width: int) -> Image.Image:
    height = round(figure.height * width / figure.width)
    return figure.resize((width, height), Image.Resampling.LANCZOS)


def tile(figure: Image.Image, size: int, share: float = FULL,
         colors: tuple[tuple[int, int, int], ...] = BLUE) -> Image.Image:
    """Die Figur auf den Verlauf, bündig am unteren Rand."""
    canvas = _gradient(size, size, colors)
    body = _scaled(figure, round(size * share))
    canvas.alpha_composite(body, ((size - body.width) // 2, size - body.height))
    return canvas


def rounded(image: Image.Image, corner: float = CORNER) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, image.width - 1, image.height - 1), round(image.width * corner), fill=255)
    out = image.copy()
    out.putalpha(mask)
    return out


def tinted(figure: Image.Image, size: int) -> Image.Image:
    """Das „getönte" iOS-Icon: Graustufen auf Schwarz. Das System legt die
    Tönung über die Helligkeit — Schwarz bleibt Grund, Weiß wird Farbe."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    body = _scaled(figure, round(size * FULL))
    gray = ImageOps.grayscale(body.convert("RGB")).convert("RGBA")
    gray.putalpha(body.getchannel("A"))
    canvas.alpha_composite(gray, ((size - gray.width) // 2, size - gray.height))
    return canvas


def _opaque(image: Image.Image) -> Image.Image:
    """Der App Store lehnt ein Icon mit Alphakanal ab."""
    return image.convert("RGB")


# ── Vorschaubilder fürs Teilen ─────────────────────────────────────────


@dataclass
class Fonts:
    title: ImageFont.FreeTypeFont
    lead: ImageFont.FreeTypeFont
    body: ImageFont.FreeTypeFont
    pill: ImageFont.FreeTypeFont


def _fonts(social: Path, title_size: int, lead_size: int, body_size: int) -> Fonts:
    folder = social / "assets" / "fonts"
    return Fonts(
        title=ImageFont.truetype(str(folder / "BricolageGrotesque-700.ttf"), title_size),
        lead=ImageFont.truetype(str(folder / "Inter-700.ttf"), lead_size),
        body=ImageFont.truetype(str(folder / "Inter-400.ttf"), body_size),
        pill=ImageFont.truetype(str(folder / "Inter-700.ttf"), 30),
    )


def _waves(canvas: Image.Image) -> None:
    """Leise Wellenlinien im unteren Drittel — die Linien des alten Bilds."""
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    width, height = canvas.size
    for i in range(5):
        top = height - 205 + i * 52
        draw.ellipse((-width * 0.6, top, width * 1.6, top + 900),
                     outline=(255, 255, 255, 34 - i * 4), width=2)
    canvas.alpha_composite(layer)


def _shadowed(canvas: Image.Image, image: Image.Image, at: tuple[int, int]) -> None:
    shadow = Image.new("RGBA", (image.width + 80, image.height + 80), (0, 0, 0, 0))
    shadow.paste((4, 30, 56, 120), (40, 52), image.getchannel("A"))
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)), (at[0] - 40, at[1] - 40))
    canvas.alpha_composite(image, at)


def og_share(figure: Image.Image, social: Path) -> Image.Image:
    """``public/og-teilen.png``: das Vorschaubild geteilter Antworten."""
    canvas = _gradient(1200, 630, ((13, 121, 199), (4, 52, 96)), diagonal=False)
    _waves(canvas)
    icon = rounded(tile(figure, 264))
    _shadowed(canvas, icon, (98, 183))
    fonts = _fonts(social, 112, 40, 36)
    draw = ImageDraw.Draw(canvas)
    draw.text((422, 312), "Ratslotse", font=fonts.title, fill="white", anchor="ls")
    for row, line in enumerate(("Frag den Rat — Antworten aus echten",
                                "Ratsbeschlüssen, mit Quellen.")):
        draw.text((424, 372 + row * 52), line, font=fonts.body,
                  fill=(214, 232, 246), anchor="ls")
    return canvas


def og_start(group: Image.Image, social: Path) -> Image.Image:
    """``app/opengraph-image.png``: die Startseite, geteilt."""
    canvas = _gradient(1200, 630, BLUE)
    _waves(canvas)
    figure = _scaled(group, 480)
    _shadowed(canvas, figure, (1200 - figure.width - 20, 630 - figure.height - 34))
    fonts = _fonts(social, 112, 42, 28)
    draw = ImageDraw.Draw(canvas)
    draw.text((80, 190), "Ratslotse", font=fonts.title, fill="white", anchor="ls")
    for row, line in enumerate(("Was beschließt", "eigentlich der Rat?")):
        draw.text((82, 268 + row * 54), line, font=fonts.lead, fill="white", anchor="ls")
    for row, line in enumerate(("Beschlüsse des Oldenburger Stadtrats —",
                                "durchsuchbar, verständlich, mit KI-Antworten.")):
        draw.text((82, 404 + row * 42), line, font=fonts.body,
                  fill=(214, 232, 246), anchor="ls")
    label = "ratslotse.de"
    left, top, right, bottom = draw.textbbox((0, 0), label, font=fonts.pill)
    pill_w, pill_h = right - left + 100, 64
    draw.rounded_rectangle((80, 472, 80 + pill_w, 472 + pill_h), pill_h // 2, fill=SIGNAL)
    draw.text((80 + pill_w / 2, 472 + pill_h / 2), label, font=fonts.pill,
              fill="white", anchor="mm")
    return canvas


# ── Ablauf ─────────────────────────────────────────────────────────────


def targets(figure: Image.Image, group: Image.Image, social: Path) -> dict[Path, Image.Image]:
    app_icon = IOS_ASSETS / "AppIcon.appiconset"
    out: dict[Path, Image.Image] = {
        # Web: Next liest app/icon.png und app/apple-icon.png selbst ein.
        WEB / "app" / "icon.png": rounded(tile(figure, 512)),
        WEB / "app" / "apple-icon.png": _opaque(tile(figure, 180)),
        WEB / "public" / "icon-192.png": tile(figure, 192),
        WEB / "public" / "icon-512.png": tile(figure, 512, MASKABLE),
        # Die Marke im Kopf jeder Seite (components/brand.tsx) und in jeder
        # Mail (kern/digest_email.py) — mit eingebrannter Rundung, weil
        # Outlook border-radius nicht kennt.
        WEB / "public" / "logo-mark.png": rounded(tile(figure, 256)),
        WEB / "app" / "opengraph-image.png": _opaque(og_start(group, social)),
        WEB / "public" / "og-teilen.png": _opaque(og_share(figure, social)),
        ROOT / "docs-site" / "public" / "favicon.png": rounded(tile(figure, 256)),
        app_icon / "AppIcon-1024.png": _opaque(tile(figure, 1024)),
        app_icon / "AppIcon-1024-dark.png": _opaque(tile(figure, 1024, colors=NIGHT)),
        app_icon / "AppIcon-1024-tinted.png": _opaque(tinted(figure, 1024)),
        IOS_ASSETS / "AppIconPreview.imageset" / "AppIconPreview.png": _opaque(tile(figure, 1024)),
        # Das Logo der Instagram-Karten drüben ist dieselbe Kachel.
        social / "assets" / "marke" / "logo-mark.png": rounded(tile(figure, 256)),
    }
    return out


def overview(images: dict[Path, Image.Image], folder: Path) -> Path:
    """Ein Blatt mit allen Größen auf hellem und dunklem Grund."""
    folder.mkdir(parents=True, exist_ok=True)
    icon = images[WEB / "app" / "icon.png"]
    sizes = (256, 128, 64, 32, 16)
    width = sum(sizes) + 40 * (len(sizes) + 1)
    sheet = Image.new("RGBA", (width, 2 * 296), (246, 249, 251, 255))
    sheet.paste((9, 17, 27, 255), (0, 296, width, 2 * 296))
    for row in range(2):
        x = 40
        for size in sizes:
            small = icon.resize((size, size), Image.Resampling.LANCZOS)
            sheet.alpha_composite(small, (x, row * 296 + (296 - size) // 2))
            x += size + 40
    path = folder / "icons.png"
    sheet.save(path)
    for target, image in images.items():
        if target.name in ("opengraph-image.png", "og-teilen.png"):
            image.save(folder / target.name)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--social", help="Checkout von ratslotse-social")
    parser.add_argument("--vorschau", help="Ordner für ein Übersichtsblatt")
    args = parser.parse_args(argv)

    social = _find_social(args.social)
    marke = social / "assets" / "marke"
    figure = _load(marke / "lotti-app-icon.png")
    group = _load(marke / "lotti-splash.png")
    print(f"Figur aus {marke}")

    images = targets(figure, group, social)
    for path, image in images.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, optimize=True)
        shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        print(f"  {shown}  {image.width}×{image.height}")
    if args.vorschau:
        print("Vorschau:", overview(images, Path(args.vorschau)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
