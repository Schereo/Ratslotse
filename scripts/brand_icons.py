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
auf den sichtbaren Inhalt beschnitten. Dieses Skript setzt die Figur in
eine kleine Szene — Himmel, Sonne angeschnitten in der Ecke, drei Möwen,
davor das Meer (Tims Wahl 25.11.26) — und schreibt jede Größe, die
irgendwo gebraucht wird.

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
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web" / "frontend"
IOS_ASSETS = ROOT / "ios" / "Resources" / "Assets.xcassets"

RGB = tuple[int, int, int]

#: Hafenblau, diagonal — der Grund der Vorschaubilder.
BLUE: tuple[RGB, RGB] = ((11, 114, 184), (10, 61, 102))
#: Signal-Orange der Designsprache.
SIGNAL: RGB = (246, 102, 35)


@dataclass(frozen=True)
class Scene:
    """Der Grund einer Kachel: Himmel, Sonne in der Ecke, Möwen, Meer."""

    sky: tuple[RGB, RGB]
    sun: tuple[RGB, RGB]
    halo: RGB
    gull: RGB
    sea: tuple[RGB, RGB, RGB]
    foam: int


#: Tag: Hafenblau oben, zum Horizont heller; die Sonne in Gold und
#: Signal-Orange.
DAY = Scene(sky=((10, 92, 168), (64, 160, 222)), sun=((255, 200, 92), (248, 118, 44)),
            halo=(255, 214, 140), gull=(255, 255, 255),
            sea=((16, 98, 168), (10, 70, 124), (6, 48, 90)), foam=170)
#: Das dunkle iOS-Icon: dieselbe Szene bei Nacht, die Sonne als blasser Mond.
NIGHT = Scene(sky=((9, 22, 38), (24, 54, 86)), sun=((252, 226, 160), (236, 176, 86)),
              halo=(250, 220, 160), gull=(196, 214, 232),
              sea=((16, 44, 72), (11, 32, 54), (7, 21, 37)), foam=110)

#: Sonne: Mitte und Radius im Verhältnis zur Kachel. Sie sitzt angeschnitten
#: in der Ecke oben rechts — Tims Wahl am 25.11.26 aus fünf Varianten.
SUN = (0.92, 0.07, 0.16)
#: Möwen oben links: Mitte und Spannweite. Links neben der Mütze ist der
#: einzige freie Himmel; kleiner heißt weiter weg.
GULLS = ((0.145, 0.150, 0.110), (0.255, 0.082, 0.075), (0.075, 0.250, 0.060))
#: Wellen von hinten nach vorn: Höhe, Ausschlag, Wellenlänge, Phase, mit
#: Schaumkrone. Sie decken den Körper ab, wo er aus dem Render läuft —
#: Lotti schwimmt, wie eine Möwe das tut.
WAVES = ((0.80, 0.018, 0.42, 0.0, True), (0.87, 0.016, 0.33, 1.7, True),
         (0.94, 0.012, 0.27, 3.1, False))

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


def _glow(canvas: Image.Image, center: tuple[float, float], radius: float,
          color: RGB, alpha: int, blur: float) -> None:
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    x, y = center
    ImageDraw.Draw(layer).ellipse((x - radius, y - radius, x + radius, y + radius),
                                  fill=(*color, alpha))
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def _sun(canvas: Image.Image, scene: Scene) -> None:
    size = canvas.width
    x, y, r = (round(v * size) for v in SUN)
    _glow(canvas, (x, y), r * 2.2, (230, 245, 255), 60, size * 0.05)
    _glow(canvas, (x, y), r * 1.35, scene.halo, 110, size * 0.02)
    disc = _gradient(2 * r, 2 * r, scene.sun, diagonal=False)
    mask = Image.new("L", disc.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=255)
    disc.putalpha(mask)
    canvas.alpha_composite(disc, (x - r, y - r))


def _gulls(canvas: Image.Image, color: RGB) -> None:
    """Möwen als zwei geschwungene Flügel, die sich in der Mitte treffen."""
    size = canvas.width
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for fx, fy, fspan in GULLS:
        x, y, span = fx * size, fy * size, fspan * size
        width = max(2, round(span * 0.095))
        for side in (-1, 1):
            # Quadratische Kurve: Mitte → Bogen nach oben → Flügelspitze.
            p0, p1, p2 = (x, y), (x + side * span * 0.24, y - span * 0.40), (x + side * span / 2, y - span * 0.06)
            points = [((1 - s) ** 2 * p0[0] + 2 * (1 - s) * s * p1[0] + s * s * p2[0],
                       (1 - s) ** 2 * p0[1] + 2 * (1 - s) * s * p1[1] + s * s * p2[1])
                      for s in (i / 24 for i in range(25))]
            draw.line(points, fill=(*color, 235), width=width, joint="curve")
            for px, py in (points[0], points[-1]):
                draw.ellipse((px - width / 2, py - width / 2, px + width / 2, py + width / 2),
                             fill=(*color, 235))
    canvas.alpha_composite(layer)


def _sea(canvas: Image.Image, scene: Scene) -> None:
    size = canvas.width
    for (fy, famp, fwave, phase, foam), color in zip(WAVES, scene.sea):
        y0, amp, wave = fy * size, famp * size, fwave * size
        line = [(float(x), y0 + amp * math.sin(2 * math.pi * x / wave + phase))
                for x in range(-10, size + 11, max(2, size // 256))]
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        draw.polygon([*line, (size + 10, size + 10), (-10, size + 10)], fill=(*color, 255))
        if foam:
            draw.line(line, fill=(255, 255, 255, scene.foam), width=round(size * 0.012),
                      joint="curve")
        canvas.alpha_composite(layer)


def tile(figure: Image.Image, size: int, share: float = FULL,
         scene: Scene = DAY) -> Image.Image:
    """Die Kachel: Himmel, Sonne, Möwen, die Figur bündig am unteren Rand,
    davor das Meer. Doppelt so groß gezeichnet und dann verkleinert — sonst
    werden Wellenkanten und Möwen in den kleinen Größen treppig."""
    big = max(size * 2, 1024)
    canvas = _gradient(big, big, scene.sky, diagonal=False)
    _sun(canvas, scene)
    _gulls(canvas, scene.gull)
    body = _scaled(figure, round(big * share))
    canvas.alpha_composite(body, ((big - body.width) // 2, big - body.height))
    _sea(canvas, scene)
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def rounded(image: Image.Image, corner: float = CORNER) -> Image.Image:
    # Maske vierfach groß zeichnen und verkleinern: Sonst ist die Rundung
    # treppig, und das sieht man im Browser-Tab zuerst.
    big = (image.width * 4, image.height * 4)
    mask = Image.new("L", big, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, big[0] - 1, big[1] - 1), round(big[0] * corner), fill=255)
    mask = mask.resize(image.size, Image.Resampling.LANCZOS)
    out = image.copy()
    out.putalpha(mask)
    return out


def tinted(figure: Image.Image, size: int) -> Image.Image:
    """Das „getönte" iOS-Icon: die Nachtszene in Graustufen. Das System legt
    die Tönung über die Helligkeit — der dunkle Himmel bleibt Grund, Lotti,
    Mond und Schaum werden Farbe."""
    return ImageOps.grayscale(tile(figure, size, scene=NIGHT).convert("RGB")).convert("RGB")


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
        app_icon / "AppIcon-1024-dark.png": _opaque(tile(figure, 1024, scene=NIGHT)),
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
