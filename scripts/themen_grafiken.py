"""Die kleinen Bilder der Stadtthemen im Einrichtungs-Assistenten erzeugen.

Jedes kuratierte Stadtthema (``council/city_topics.py``) bekommt ein Bild: flach,
dünne dunkelblaue Kontur, Markenfarben — und bei den meisten spielt ein Gast
aus Lottis Welt mit (Lotti, Küken, Krissi; Referenz ``themen_referenz.png``).
Der erste Anlauf im glänzenden 3D-Stil passte nicht zur ruhigen Oberfläche
(Tim, 01.10.2026).

Anlass der Bilder ist ein Befund vom 30.09.2026: Neue Konten wählten fast nur Stadtteile, weil
„Bus und Bahn" als Pille neben einem Stadtteil abstrakt wirkt. Ein Bild macht
ein Thema greifbar, bevor man den Namen gelesen hat.

Die Bilder liegen als Dateien in ``web/frontend/public/themen/<key>.webp`` im
Repo — erzeugt wird EINMAL von Hand, nicht zur Laufzeit. Das Skript gehört
deshalb nicht in ``kern/jobs.py``: Es ist ein Werkzeug, kein Cron.

    .venv/bin/python scripts/themen_grafiken.py                # Plan, kostet nichts
    .venv/bin/python scripts/themen_grafiken.py --erzeugen     # alle fehlenden
    .venv/bin/python scripts/themen_grafiken.py --erzeugen --nur cycling,culture
    .venv/bin/python scripts/themen_grafiken.py --erzeugen --neu   # vorhandene ersetzen
    .venv/bin/python scripts/themen_grafiken.py --satz gremien --erzeugen   # die Ausschüsse

Der Schlüssel kommt aus ``OPENROUTER_API_KEY``. Jedes Bild kostet den Preis
eines Bildmodell-Aufrufs (Größenordnung vier Cent); ``--modell`` tauscht das
Modell. Nichts davon läuft in der Testsuite.
"""
from __future__ import annotations

import argparse
import base64
import io
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZIEL = ROOT / "web" / "frontend" / "public" / "themen"
ZIEL_GREMIEN = ROOT / "web" / "frontend" / "public" / "gremien"
REFERENZ = Path(__file__).resolve().parent / "themen_referenz.png"

MODELL = "google/gemini-3.1-flash-image"
#: Kantenlänge der abgelegten Datei. Im Assistenten steht das Bild bei 56 bis
#: 72 px; 256 deckt die dreifache Pixeldichte ab und bleibt bei ~10 KB.
KANTE = 256

#: Der Stil, EINMAL für alle. Ein Bild je Motiv ist nur dann eine Familie, wenn
#: der Stil nicht je Motiv neu erfunden wird.
STIL = (
    "A simple flat 2D vector illustration of {motiv}, in the style of a clean "
    "modern app icon set: minimal geometric shapes, solid flat colors, a thin "
    "dark navy outline (#0b2a45) of even weight, slightly rounded corners. "
    "Absolutely no gloss, no highlights, no reflections, no gradients, no "
    "shading, no 3D, no shadow. One single centered object filling about 65 "
    "percent of the square frame. Palette limited to harbor blue (#0764a6), "
    "signal orange (#f66623), white and warm cream, with {farbe} as the main "
    "accent. The background is one flat, plain, very light {hintergrund} "
    "color with nothing on it. No text, no letters, no numbers, no real "
    "humans, no watermark.{cameo}"
)

#: Der Zusatz, wenn eine Figur aus Lottis Welt mitspielt. Das Referenzbild
#: (`themen_referenz.png`, ein Rendering aus dem Lotti-Studio) bekommt das
#: Modell mitgeschickt; die Figuren werden im flachen Stil NEU GEZEICHNET, nicht
#: abgepaust — sie müssen erkennbar bleiben, aber zur Kontur passen.
CAMEO = (
    " The attached reference image shows the mascot family of the app: LOTTI, "
    "a chubby white seagull with a navy pilot cap with a gold compass badge and "
    "orange beak and feet; a small fluffy white chick; and KRISSI, a small "
    "orange crab. Redraw {wer} in the same flat outline style as the rest of "
    "the picture (thin navy outline, flat colors, no shading), small in the "
    "scene, {was}. Keep the character recognizable, do not copy the 3D look."
)

#: key aus ``council/city_topics.py`` → (Motiv, Akzentfarbe, Hintergrund).
#: Wer wo mitspielt — nicht überall: Nur etwa zwei Drittel der Bilder haben
#: einen Gast, sonst wäre es ein Muster statt einer Überraschung.
GAESTE: dict[str, tuple[str, str]] = {
    "cycling": ("Lotti with her cap", "sitting in the front basket of the bicycle"),
    "pools": ("Krissi the crab", "sitting on top of the swim ring waving a claw"),
    "green": ("the small chick", "sitting on the bench under the tree"),
    "childcare": ("the small chick", "standing on top of the block stack instead of a teddy bear"),
    "culture": ("Lotti with her cap", "peeking out from behind the curtain"),
    "transit": ("Lotti with her cap", "looking out of the bus window"),
    "housing": ("the small chick", "standing in front of the door of the smallest house"),
    "fire": ("Lotti with her cap", "sitting in the driver seat of the fire engine"),
    "airfield": ("Lotti with her cap", "sitting in the cockpit of the plane"),
    "schools": ("the small chick", "standing at the entrance holding a pencil"),
    "youth": ("the small chick", "sliding down the slide"),
    "climate": ("Krissi the crab", "holding the green leaf sprout in a claw"),
    "waste": ("Krissi the crab", "climbing on the edge of the recycling bin"),
    "roads": ("Krissi the crab", "walking across the bridge"),
    "sports": ("the small chick", "sitting on top of the ball"),
}

#: Die Ausschüsse (Schritt 1 des Assistenten): Hier ist Lotti die HAUPTFIGUR mit
#: einem Requisit je Sachbereich — Tims alter Wunsch „eine Lotti je Ausschuss".
#: Schlüssel und Zuordnung zu den Gremiennamen: ``web/frontend/lib/committees.ts``.
#: Eintrag: (Requisit, Lotti-Rolle, Akzentfarbe, Hintergrund).
GREMIEN: dict[str, tuple[str, str, str, str]] = {
    "council": ("a small wooden lectern with a little gavel and a tiny town hall building behind", "standing behind the lectern", "orange", "light sky blue"),
    "executive": ("a thick closed folder with a padlock on it and a small desk lamp", "sitting at a small desk next to it", "blue", "light lavender"),
    "general": ("a clipboard with a checklist and a big rubber stamp", "holding the stamp in a wing", "orange", "light warm beige"),
    "finance": ("a piggy bank and a short stack of coins", "standing next to the piggy bank, dropping a coin in", "orange", "light peach"),
    "integration": ("a round globe on a little stand with a heart on it", "standing beside the globe together with the small chick, both looking at it", "blue", "light aqua"),
    "green": ("a young tree in a pot and a watering can", "watering the tree with the can", "green", "light mint"),
    "planning": ("a rolled-up city plan and a small model house", "wearing a yellow hard hat over her cap, holding the plan", "orange", "light sky blue"),
    "business": ("a briefcase and an open laptop", "standing next to them, one wing resting on the laptop", "blue", "light lavender"),
    "waste": ("a recycling bin with a green arrow and a litter picker stick", "holding the litter picker", "green", "light mint"),
    "buildings": ("a small brick wall, a spirit level and a wrench", "holding the wrench next to the wall", "orange", "light warm beige"),
    "youth": ("a flying kite with a ribbon tail", "holding the kite string together with the small chick", "orange", "light yellow"),
    "culture": ("a music note, a paint palette with a brush and a small spotlight", "standing next to the palette, conducting with a wing", "orange", "light lavender"),
    "school": ("a school bag, an open book and a pencil", "standing next to the bag, reading the book", "orange", "light yellow"),
    "social": ("a big heart-shaped cushion and a steaming cup", "sitting on the cushion with the small chick, sharing it", "orange", "light peach"),
    "sport": ("a whistle, a medal on a ribbon and a small cone", "wearing the medal around her neck, blowing the whistle", "orange", "light green"),
    "traffic": ("a zebra crossing, a round traffic sign and a bicycle helmet", "wearing the bicycle helmet over her cap, standing on the crossing", "blue", "light sky blue"),
}

MOTIVE: dict[str, tuple[str, str, str]] = {
    "cycling": ("a cheerful little city bicycle with a front basket", "orange", "sky blue"),
    "stadium": ("a small football stadium with four floodlight towers and green pitch", "green", "light grey-blue"),
    "pools": ("a round swim ring floating on a small blob of water with a tiny wave", "orange", "light aqua"),
    "green": ("a round leafy tree with a short trunk and a small bench", "green", "light mint"),
    "childcare": ("a stack of colorful toy building blocks with a little teddy bear on top", "orange", "cream yellow"),
    "culture": ("a pair of theatre masks, one smiling and one sad, on a little curtain", "orange", "light lavender"),
    "transit": ("a cute rounded city bus seen from the front-side with big headlights", "blue", "light sky blue"),
    "sports": ("a round black-and-white soccer ball (European football, not an American football) next to a whistle and a small trophy cup", "orange", "light green"),
    "housing": ("three small cozy houses with gabled roofs and round windows", "orange", "light peach"),
    "fire": ("a chubby red fire engine with a little ladder and a blue light", "red", "light grey-blue"),
    "downtown": ("a row of three narrow shop houses with striped awnings on a cobbled street", "orange", "light warm beige"),
    "airfield": ("a little propeller airplane with round body, seen from the side", "orange", "light sky blue"),
    "schools": ("a school building with a small clock tower next to a pencil", "orange", "light yellow"),
    "youth": ("a playground slide with a small swing, bright and friendly", "orange", "light mint"),
    "climate": ("a smiling sun with a small cloud and a green leaf sprout", "orange", "light sky blue"),
    "waste": ("a round recycling bin with a green arrow symbol and a little leaf", "green", "light mint"),
    "heat": ("a solar panel tilted towards a small sun, with a little flame-shaped heat drop", "orange", "light peach"),
    "roads": ("a small arched stone bridge over a blue stream with a tiny road sign", "blue", "light warm beige"),
    "business": ("a small shop with a striped awning and a round potted plant, open sign as plain shape", "blue", "light lavender"),
    "digital": ("a chubby laptop with a big check mark shape on the screen", "blue", "light sky blue"),
}


def _schluessel() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    # Die .env steht im Haupt-Checkout, nicht im Worktree.
    for kandidat in (ROOT / ".env", *ROOT.parents):
        datei = kandidat if kandidat.name == ".env" else kandidat / ".env"
        if datei.is_file():
            for zeile in datei.read_text().splitlines():
                if zeile.startswith("OPENROUTER_API_KEY="):
                    return zeile.split("=", 1)[1].strip().strip("'\"")
    sys.exit("Kein OPENROUTER_API_KEY — weder in der Umgebung noch in einer .env.")


def ohne_rahmen(bild):
    """Schneidet den weißen Rahmen mit runden Ecken weg, den das Modell manchmal
    um die Kachel zeichnet (Wärmewende, Schulen und Straßen am 01.10.2026).

    Erkannt wird er an einer fast weißen Ecke bei zugleich getönter Randmitte:
    Die Kachel soll bis in die Ecken tragen, der Rahmen fiele sonst im Assistenten
    als heller Fleck auf. Die Motive füllen etwa 65 % des Bildes, acht Prozent
    Rand gehen also nie auf Kosten des Motivs."""
    breite, hoehe = bild.size
    ecken = [bild.getpixel(p) for p in ((2, 2), (breite - 3, 2), (2, hoehe - 3), (breite - 3, hoehe - 3))]
    rand = bild.getpixel((breite // 2, 2))
    if any(min(e) > 240 for e in ecken) and min(rand) < 240:
        d = int(min(breite, hoehe) * 0.08)
        return bild.crop((d, d, breite - d, hoehe - d))
    return bild


#: Wie CAMEO, nur größer: Im Gremien-Satz ist Lotti das Bild, nicht der Gast.
HAUPTFIGUR = (
    " The attached reference image shows the mascot family of the app: LOTTI, "
    "a chubby white seagull with a navy pilot cap with a gold compass badge and "
    "orange beak and feet; a small fluffy white chick; and KRISSI, a small "
    "orange crab. LOTTI is the MAIN CHARACTER of this picture, drawn large and "
    "clearly recognizable: she is {was}. Redraw her in the same flat outline "
    "style as the props (thin navy outline, flat colors, no shading); do not "
    "copy the 3D look of the reference. Lotti and the props together fill "
    "about 70 percent of the frame, fully visible with generous margin on all "
    "sides, nothing cropped at the edges."
)


def erzeuge(key: str, modell: str, motiv: tuple[str, str, str],
            gast: tuple[str, str] | None = None, hauptfigur: bool = False) -> bytes:
    """Ein Bild holen und als WebP mit ``KANTE`` Pixeln zurückgeben."""
    import httpx
    from PIL import Image

    beschreibung, farbe, hintergrund = motiv
    text = STIL.format(
        motiv=beschreibung, farbe=farbe, hintergrund=hintergrund,
        cameo=(HAUPTFIGUR.format(was=gast[1]) if hauptfigur else CAMEO.format(wer=gast[0], was=gast[1]))
        if gast else "")
    if gast:
        referenz = base64.b64encode(REFERENZ.read_bytes()).decode()
        inhalt: str | list = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{referenz}"}},
        ]
    else:
        inhalt = text
    antwort = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": modell,
            "modalities": ["image", "text"],
            "messages": [{"role": "user", "content": inhalt}],
        },
        timeout=180,
    )
    antwort.raise_for_status()
    nachricht = antwort.json()["choices"][0]["message"]
    bilder = nachricht.get("images") or []
    if not bilder:
        raise RuntimeError(f"Modell lieferte kein Bild: {str(nachricht)[:200]}")
    url = bilder[0]["image_url"]["url"]
    roh = base64.b64decode(url.split(",", 1)[1])
    bild = Image.open(io.BytesIO(roh)).convert("RGB")
    bild = ohne_rahmen(bild)
    # Mittig quadratisch zuschneiden, dann verkleinern.
    seite = min(bild.size)
    links, oben = (bild.width - seite) // 2, (bild.height - seite) // 2
    bild = bild.crop((links, oben, links + seite, oben + seite)).resize((KANTE, KANTE), Image.Resampling.LANCZOS)
    puffer = io.BytesIO()
    bild.save(puffer, "WEBP", quality=86, method=6)
    return puffer.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--erzeugen", action="store_true", help="wirklich Bilder holen (kostet)")
    ap.add_argument("--neu", action="store_true", help="vorhandene Dateien ersetzen")
    ap.add_argument("--nur", default="", help="kommagetrennte Schlüssel")
    ap.add_argument("--modell", default=MODELL)
    ap.add_argument("--satz", choices=("themen", "gremien"), default="themen")
    args = ap.parse_args()

    sys.path.insert(0, str(ROOT))
    from council.city_topics import CITY_TOPICS

    gremien = args.satz == "gremien"
    ziel = ZIEL_GREMIEN if gremien else ZIEL
    if gremien:
        # Requisit, Rolle, Farbe, Hintergrund → (Motiv, Gast) für `erzeuge`.
        motive = {k: (v[0], v[2], v[3]) for k, v in GREMIEN.items()}
        gaeste = {k: ("Lotti with her cap", v[1]) for k, v in GREMIEN.items()}
        keys = list(GREMIEN)
    else:
        motive, gaeste = MOTIVE, GAESTE
        keys = [t.key for t in CITY_TOPICS]
        fehlt = [k for k in keys if k not in MOTIVE]
        if fehlt:
            sys.exit(f"Kein Motiv für: {', '.join(fehlt)} — in MOTIVE ergänzen.")
    wahl = [k.strip() for k in args.nur.split(",") if k.strip()] or keys
    unbekannt = [k for k in wahl if k not in motive]
    if unbekannt:
        sys.exit(f"Unbekannter Schlüssel: {', '.join(unbekannt)}")

    offen = [k for k in wahl if args.neu or not (ziel / f"{k}.webp").exists()]
    print(f"{len(offen)} von {len(wahl)} Bildern offen: {', '.join(offen) or '—'}")
    if not args.erzeugen or not offen:
        if offen:
            print(f"Trockenlauf. Mit --erzeugen werden sie geholt (Modell: {args.modell}).")
        return 0

    key = _schluessel()
    ziel.mkdir(parents=True, exist_ok=True)
    for k in offen:
        t0 = time.time()
        try:
            daten = erzeuge(key, args.modell, motive[k], gaeste.get(k), hauptfigur=gremien)
        except Exception as e:  # noqa: BLE001 — ein Motiv darf die übrigen nicht aufhalten
            print(f"  {k}: FEHLER {e}")
            continue
        (ziel / f"{k}.webp").write_bytes(daten)
        print(f"  {k}: {len(daten) / 1024:.1f} KB in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
