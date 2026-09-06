#!/usr/bin/env python3
"""Den Splash der iOS-App aus den Bausteinen von ratslotse-social setzen.

    python3 ios/scripts/make_splash.py                 # schreibt die sechs PNGs
    python3 ios/scripts/make_splash.py --vorschau /tmp/splash   # + Handy-Ausschnitte
    python3 ios/scripts/make_splash.py --social ~/Pfad/zu/ratslotse-social

WOHER DAS BILD KOMMT. Bis 09/2026 lagen die sechs Dateien in
``Resources/Assets.xcassets/Splash.imageset/`` ohne Ableitung: ein
3D-Lotti-Render, darüber eine 3D-Sonne, darunter drei 3D-Wellenlinien —
zusammengesetzt von Hand, nirgends nachvollziehbar. Die Sonne und die
Wellen passten in ihrem plastischen Look nicht zum Rest (Tims Befund
06.09.26). Jetzt entsteht der Splash aus denselben Bausteinen wie die
Instagram-Karten in ``ratslotse-social``: leiser Wellengrund, weiches
Licht, Möwen als zwei Bögen, Wogen am unteren Rand — gezeichnet mit Pillow
in den Farben der Designsprache, kein Bildgenerator. Lotti selbst ist ein
Render aus demselben Studio: die Szene ``splash`` (Hero-Ansicht, zugewandt,
mit den gewölbten Freude-Brauen), über ``studio/marke.py`` nach
``assets/marke/lotti-splash.png`` gelegt. Die Jubel-Szene der App war der
erste Stand; die Helden-Pose der Karten wirkte mit ihrem „hört zu" auf dem
Splash traurig (Tim, 06.09.26).

DIE LEINWAND IST 1400 PUNKT GROSS, UND DAS IST KEIN ZUFALL. ``UILaunchScreen``
zeigt das Bild ungeskaliert und zentriert; was über den Bildschirm
hinausragt, wird abgeschnitten, und was fehlt, füllt ``SplashBackground``.
Wogen, die am unteren Bildschirmrand stehen sollen, müssen deshalb bis zum
unteren Rand der LEINWAND laufen — und die Leinwand muss mindestens so hoch
sein wie das höchste Gerät (iPad 13": 1.376 pt), sonst zeigt sich unter den
Wogen ein Streifen Seitenfarbe. Alles Wichtige sitzt in der Mitte auf einem
Streifen von 375 × 667 pt, dem kleinsten Bildschirm, den die App kennt.

Der Grund des Bildes ist exakt die Seitenfarbe (``RatsColor.page`` bzw.
``SplashBackground``), damit die Bildkante auf dem iPad keine Naht zieht.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HIER = Path(__file__).resolve().parent
IOS = HIER.parent
ASSETS = IOS / "Resources" / "Assets.xcassets"
ZIEL = ASSETS / "Splash.imageset"
FONTS = IOS / "Resources" / "Fonts"

#: Seitenlänge der Leinwand in Punkten (s. Modul-Docstring).
LEINWAND = 1400
#: Der kleinste Bildschirm (iPhone SE, Punkte): Alles Tragende bleibt in
#: diesem mittig liegenden Ausschnitt.
KLEINSTER = (375, 667)

# Farben aus der Designsprache (web/frontend/DESIGNSPRACHE.md §2) — dieselben
# Werte wie RatsColor in RatslotseDesign/DesignTokens.swift.
#: Die Lagen der Sonne: (Radius-Faktor, Farbe, Alpha) — die Werte aus
#: ``bausteine.sonne``. Nachts dieselbe Sonne in kühlen Tönen: ein Mond.
#: Warmes Licht auf Nachtblau wird braun, nicht golden.
SONNE_HELL = [(3.4, (255, 198, 142), 40), (1.8, (255, 206, 152), 62), (1.0, (255, 168, 92), 168)]
SONNE_DUNKEL = [(3.4, (150, 190, 225), 24), (1.8, (190, 214, 236), 52), (1.0, (236, 243, 249), 196)]

HELL = {
    "seite": (0xF6, 0xFA, 0xFC),
    "text": (0x0D, 0x21, 0x32),
    "signal": (0xF0, 0x5A, 0x22),
    # Wogen von hinten nach vorn — die Töne der Vorstellungs-Reihe
    # (ratslotse_social/geschichten.py, _streifen_grund).
    "wogen": [((205, 52, 86), 225), ((205, 56, 79), 215), ((206, 58, 71), 200)],
    "muster_alpha": 13,
    "sonne": SONNE_HELL,
}
DUNKEL = {
    "seite": (0x09, 0x11, 0x1B),
    "text": (0xF3, 0xF8, 0xFA),
    "signal": (0xFA, 0x74, 0x40),
    # Karte, Rahmen, Rahmen-interaktiv des dunklen Themas.
    "wogen": [((212, 42, 11), 235), ((211, 36, 17), 225), ((211, 36, 21), 215)],
    "muster_alpha": 16,
    "sonne": SONNE_DUNKEL,
}


def _social_finden(angabe: str | None) -> Path:
    """Den Checkout von ratslotse-social finden: Argument, Umgebung, dann
    ein Geschwister-Verzeichnis irgendwo oberhalb (deckt Haupt-Checkout wie
    Worktree unter .claude/worktrees/ ab)."""
    kandidaten = [angabe, os.environ.get("RATSLOTSE_SOCIAL")]
    for k in kandidaten:
        if k:
            p = Path(k).expanduser().resolve()
            if (p / "ratslotse_social" / "bausteine.py").exists():
                return p
            sys.exit(f"ratslotse-social nicht gefunden unter {p}")
    for eltern in [IOS.parent, *IOS.parent.parents]:
        p = eltern / "ratslotse-social"
        if (p / "ratslotse_social" / "bausteine.py").exists():
            return p
    sys.exit("ratslotse-social nicht gefunden — --social PFAD oder RATSLOTSE_SOCIAL setzen")


def _bausteine(social: Path):
    sys.path.insert(0, str(social))
    from ratslotse_social import bausteine, layout  # noqa: E402  (Pfad erst hier bekannt)
    return bausteine, layout


def _hsl(layout, farbe: tuple[int, int, int]) -> tuple[int, int, int]:
    return layout.hsl(*farbe)


# ------------------------------------------------------------------ Schrift

def _bricolage(px: int) -> ImageFont.FreeTypeFont:
    """Bricolage Grotesque ExtraBold aus der variablen Datei der App. Die
    optische Größe folgt dem Schriftgrad in Punkt, wie CoreText es in der
    App auch hält."""
    font = ImageFont.truetype(str(FONTS / "BricolageGrotesque-Variable.ttf"), px)
    font.set_variation_by_axes([min(96, max(12, px)), 800, 100])
    return font


def _plexmono(px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / "IBMPlexMono-Medium.ttf"), px)


def _gesperrt(d: ImageDraw.ImageDraw, mitte_x: float, y: float, text: str,
              font: ImageFont.FreeTypeFont, fill, sperrung: float) -> None:
    """Versal-Kicker mit Laufweite, zentriert. Pillow kennt keine
    Laufweite — Zeichen für Zeichen, ``sperrung`` in Pixel je Zeichen."""
    breiten = [font.getlength(z) for z in text]
    gesamt = sum(breiten) + sperrung * (len(text) - 1)
    x = mitte_x - gesamt / 2
    for z, b in zip(text, breiten):
        d.text((x, y), z, font=font, fill=fill)
        x += b + sperrung


# --------------------------------------------------------------------- Wogen

def _wogen(bild: Image.Image, layout, kaemme: list[int], farben, wellenlaenge: float,
           amplitude: float) -> None:
    """Wogen mit ausdrücklichen Kammhöhen.

    ``layout.wogen`` verteilt seine Wogen gleichmäßig zwischen dem ersten
    Kamm und der Unterkante. Auf einer Karte ist das richtig; hier läuft die
    Leinwand aber weit unter jeden Bildschirmrand hinaus (s. Docstring), und
    gleichmäßig verteilt lägen die Kämme 110 pt auseinander — Wasserflächen
    statt Wogen. Deshalb die Kämme von Hand, dieselbe Pfadfunktion.
    """
    b, h = bild.size
    lage = Image.new("RGBA", (b, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(lage)
    for i, (kamm, (farbe, alpha)) in enumerate(zip(kaemme, farben)):
        pfad = layout._wellenpfad(kamm, b, wellenlaenge / (1 + i * 0.35),
                                  amplitude * (1 - i * 0.2), phase=i * wellenlaenge / 3)
        d.polygon(pfad + [(b + wellenlaenge, h + 4), (-wellenlaenge, h + 4)],
                  fill=(*farbe, alpha))
    bild.alpha_composite(lage)


def _sonne(bild: Image.Image, x: int, y: int, radius: int,
           lagen: list[tuple[float, tuple[int, int, int], int]]) -> None:
    """Weiche Sonne: Kern, Hof, weiter Schein — drei Lagen wie
    ``bausteine.sonne`` drüben, mit denselben Radien und Farben.

    Nur der Verlauf entsteht anders: dort aus achtzehn Ringen auf einer
    winzigen Maske, die hochskaliert wird. Auf einer 1080er Karte, wo die
    Sonne am Rand steht, fällt das nicht auf; auf dem Splash steht sie frei
    über Lotti, und die hochgezogenen Ringe lesen sich als achteckige
    Lappen. Hier ist der Verlauf eine geblurte Scheibe — rund, ohne Kanten.
    """
    from PIL import ImageFilter

    for faktor, farbe, staerke in lagen:
        r = radius * faktor
        gross = round(r * 2.6)
        maske = Image.new("L", (gross, gross), 0)
        md = ImageDraw.Draw(maske)
        # Scheibe mit halbem Radius, Blur über den Rest: Der Kern bleibt
        # satt, der Rand läuft weich in den Grund aus.
        md.ellipse([gross / 2 - r * 0.5, gross / 2 - r * 0.5,
                    gross / 2 + r * 0.5, gross / 2 + r * 0.5], fill=staerke)
        maske = maske.filter(ImageFilter.GaussianBlur(r * 0.42))
        bild.paste(Image.new("RGB", (gross, gross), farbe),
                   (x - gross // 2, y - gross // 2), maske)




# --------------------------------------------------------------------- Figur

def _figur(pfad: Path, hoehe_px: int) -> Image.Image:
    """Das Render alpha-getrimmt auf Zielhöhe — wie ``studio/marke.py``
    drüben: Der fast durchsichtige Bodenschatten gehört dazu."""
    bild = Image.open(pfad).convert("RGBA")
    kasten = bild.getchannel("A").getbbox()
    if kasten:
        bild = bild.crop(kasten)
    breite = max(1, round(bild.width * hoehe_px / bild.height))
    return bild.resize((breite, hoehe_px), Image.LANCZOS)


# --------------------------------------------------------------------- Setzen

def splash(scale: int, dunkel: bool, social: Path, figur: Path) -> Image.Image:
    bausteine, layout = _bausteine(social)
    thema = DUNKEL if dunkel else HELL
    s = scale
    px = LEINWAND * s
    mitte = px / 2

    bild = Image.new("RGBA", (px, px), (*thema["seite"], 255))

    # 1. Wellenmuster über die ganze Höhe bis zu den Wogen — das Marken-
    #    Muster als Fläche, im Hellen Hafenblau, im Dunklen Weiß.
    muster_farbe = (255, 255, 255) if dunkel else _hsl(layout, (205, 92, 34))
    layout.wellenmuster(bild, (0, 930 * s), muster_farbe, alpha=thema["muster_alpha"],
                        wellenlaenge=110 * s, amplitude=5 * s, zeilenabstand=44 * s,
                        staerke=max(1, round(1.5 * s)))

    # 2. Weiches Licht mit einer Quelle: der Sonne rechts oben. Im Hellen
    #    hebt der Lichtkern die Fläche unter der Sonne an; im Dunklen bliebe
    #    davon nur ein grauer Fleck. Nachts steht dort ein Mond.
    if not dunkel:
        bausteine.licht(bild, mitte=0.58, staerke=22, hoehe_anteil=0.3)
    _sonne(bild, 836 * s, 418 * s, 30 * s, thema["sonne"])

    # 3. Möwen: drei, links der Sonne in der Höhe gestaffelt — klein und
    #    fern, größer und näher. Alle im Ausschnitt des kleinsten Geräts.
    bausteine.moewen(bild, [
        (586 * s, 446 * s, 30 * s),
        (640 * s, 414 * s, 22 * s),
        (760 * s, 372 * s, 16 * s),
    ])

    # 4. Lotti, 270 pt hoch — das Marken-Render trägt 1200 px, bei 3× also
    #    ein leichtes Verkleinern. Die Füße stehen knapp über dem ersten
    #    Wogenkamm.
    lotti = _figur(figur, 270 * s)
    bild.alpha_composite(lotti, (round(mitte - lotti.width / 2), round(492 * s)))

    # 5. Wortmarke und Kicker — dieselben Schnitte wie in der App
    #    (RatsFont.title heavy, RatsFont.mono medium mit Laufweite).
    d = ImageDraw.Draw(bild)
    titel = _bricolage(46 * s)
    d.text((mitte, 828 * s), "Ratslotse", font=titel, fill=thema["text"], anchor="mt")
    kicker = _plexmono(round(11 * s))
    _gesperrt(d, mitte, 902 * s, "OLDENBURGS RAT VERSTEHEN", kicker, thema["signal"],
              sperrung=1.3 * s)

    # 6. Wogen zuletzt: Sie liegen vor allem und laufen bis zur Unterkante.
    #    Drei Kämme, 46 pt auseinander — die Bänder der Social-Karten.
    farben = [(_hsl(layout, f), a) for f, a in thema["wogen"]]
    _wogen(bild, layout, [960 * s, 1006 * s, 1052 * s], farben,
           wellenlaenge=520 * s, amplitude=16 * s)
    return bild


def _vorschau(bild: Image.Image, scale: int, ziel: Path, name: str) -> None:
    """Handy-Ausschnitte, wie das Gerät sie zeigt: mittig, ungeskaliert."""
    for geraet, (b, h) in {"iphone": (393, 852), "se": KLEINSTER, "ipad": (1032, 1376)}.items():
        bp, hp = b * scale, h * scale
        x0 = (bild.width - bp) // 2
        y0 = (bild.height - hp) // 2
        aus = bild.crop((x0, y0, x0 + bp, y0 + hp))
        aus.convert("RGB").save(ziel / f"{name}-{geraet}.png", optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--social", help="Checkout von ratslotse-social")
    ap.add_argument("--figur", help="Lotti-Render mit Alpha (Vorgabe: assets/marke/lotti-splash.png "
                                    "aus ratslotse-social; die Jubel-Szene der App liegt unter "
                                    "Resources/Assets.xcassets/Lotti3DCelebrate.imageset/)")
    ap.add_argument("--vorschau", help="Verzeichnis für Handy-Ausschnitte (1×)")
    ap.add_argument("--nur-vorschau", action="store_true", help="Assets nicht anfassen")
    args = ap.parse_args()

    social = _social_finden(args.social)
    figur = (Path(args.figur).expanduser() if args.figur
             else social / "assets" / "marke" / "lotti-splash.png")
    if not figur.exists():
        sys.exit(f"Figur fehlt: {figur} — drüben `python3 studio/marke.py splash` laufen lassen")
    print(f"Bausteine aus {social}")
    print(f"Figur: {figur}")

    for scale in (1, 2, 3):
        for dunkel in (False, True):
            bild = splash(scale, dunkel, social, figur)
            suffix = "-dark" if dunkel else ""
            if args.vorschau:
                ziel = Path(args.vorschau)
                ziel.mkdir(parents=True, exist_ok=True)
                if scale == 3:
                    _vorschau(bild, scale, ziel, f"splash{suffix}")
                    bild.convert("RGB").resize((LEINWAND, LEINWAND), Image.LANCZOS).save(
                        ziel / f"splash{suffix}-leinwand.png", optimize=True)
            if not args.nur_vorschau:
                datei = ZIEL / f"Default@{scale}x~universal~anyany{suffix}.png"
                bild.convert("RGB").save(datei, optimize=True)
                print(f"{datei.name}: {bild.width}×{bild.height}, {datei.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
