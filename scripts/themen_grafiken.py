"""Die kleinen Bilder der Stadtthemen im Einrichtungs-Assistenten erzeugen.

Jedes kuratierte Stadtthema (``council/city_topics.py``) bekommt ein Bild in
Lottis Stil: pummelig, weich, glänzend, wie Spielzeug aus Vinyl. Der Grund ist
ein Befund vom 30.09.2026: Neue Konten wählten fast nur Stadtteile, weil
„Bus und Bahn" als Pille neben einem Stadtteil abstrakt wirkt. Ein Bild macht
ein Thema greifbar, bevor man den Namen gelesen hat.

Die Bilder liegen als Dateien in ``web/frontend/public/themen/<key>.webp`` im
Repo — erzeugt wird EINMAL von Hand, nicht zur Laufzeit. Das Skript gehört
deshalb nicht in ``kern/jobs.py``: Es ist ein Werkzeug, kein Cron.

    .venv/bin/python scripts/themen_grafiken.py                # Plan, kostet nichts
    .venv/bin/python scripts/themen_grafiken.py --erzeugen     # alle fehlenden
    .venv/bin/python scripts/themen_grafiken.py --erzeugen --nur cycling,culture
    .venv/bin/python scripts/themen_grafiken.py --erzeugen --neu   # vorhandene ersetzen

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

MODELL = "google/gemini-3.1-flash-image"
#: Kantenlänge der abgelegten Datei. Im Assistenten steht das Bild bei 56 bis
#: 72 px; 256 deckt die dreifache Pixeldichte ab und bleibt bei ~10 KB.
KANTE = 256

#: Der Stil, EINMAL für alle. Ein Bild je Motiv ist nur dann eine Familie, wenn
#: der Stil nicht je Motiv neu erfunden wird.
STIL = (
    "A cute glossy 3D vinyl-toy style icon of {motiv}. Chubby soft rounded "
    "shapes, high-gloss highlights and gentle reflections, smooth plastic "
    "surface like a collectible figurine, friendly and playful. One single "
    "centered object with a tiny soft shadow underneath, filling about 70 percent "
    "of the square frame. Palette: harbor blue (#0764a6), signal orange "
    "(#f66623), white and warm cream, with {farbe} as the main accent. The "
    "background is one flat, plain, very light {hintergrund} color with no "
    "gradient, no pattern, no frame. No text, no letters, no numbers, no "
    "people, no watermark."
)

#: key aus ``council/city_topics.py`` → (Motiv, Akzentfarbe, Hintergrund).
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


def erzeuge(key: str, modell: str, motiv: tuple[str, str, str]) -> bytes:
    """Ein Bild holen und als WebP mit ``KANTE`` Pixeln zurückgeben."""
    import httpx
    from PIL import Image

    beschreibung, farbe, hintergrund = motiv
    antwort = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": modell,
            "modalities": ["image", "text"],
            "messages": [{"role": "user", "content": STIL.format(
                motiv=beschreibung, farbe=farbe, hintergrund=hintergrund)}],
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
    args = ap.parse_args()

    sys.path.insert(0, str(ROOT))
    from council.city_topics import CITY_TOPICS

    keys = [t.key for t in CITY_TOPICS]
    fehlt = [k for k in keys if k not in MOTIVE]
    if fehlt:
        sys.exit(f"Kein Motiv für: {', '.join(fehlt)} — in MOTIVE ergänzen.")
    wahl = [k.strip() for k in args.nur.split(",") if k.strip()] or keys
    unbekannt = [k for k in wahl if k not in MOTIVE]
    if unbekannt:
        sys.exit(f"Unbekannter Schlüssel: {', '.join(unbekannt)}")

    offen = [k for k in wahl if args.neu or not (ZIEL / f"{k}.webp").exists()]
    print(f"{len(offen)} von {len(wahl)} Bildern offen: {', '.join(offen) or '—'}")
    if not args.erzeugen or not offen:
        if offen:
            print(f"Trockenlauf. Mit --erzeugen werden sie geholt (Modell: {args.modell}).")
        return 0

    key = _schluessel()
    ZIEL.mkdir(parents=True, exist_ok=True)
    for k in offen:
        t0 = time.time()
        try:
            daten = erzeuge(key, args.modell, MOTIVE[k])
        except Exception as e:  # noqa: BLE001 — ein Motiv darf die übrigen nicht aufhalten
            print(f"  {k}: FEHLER {e}")
            continue
        (ZIEL / f"{k}.webp").write_bytes(daten)
        print(f"  {k}: {len(daten) / 1024:.1f} KB in {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
