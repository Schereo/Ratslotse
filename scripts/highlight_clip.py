#!/usr/bin/env python3
"""Einen Highlight-Clip polieren: Zoom auf den Klick, sichtbarer Tipp — ohne App.

Die Clips für „Neu bei Ratslotse" (``kern/releases.py``) entstehen aus
Playwright (Browser) oder ``simctl recordVideo`` (iPhone-Simulator). Beide
liefern rohe Bildschirmaufnahmen: keinen Zeiger, keinen Zoom, und das
Teilen-Zeichen, um das es geht, ist darin acht Pixel groß.

Werkzeuge wie Recordly lösen das mit Heuristiken — sie *raten* aus der
Mausbewegung, wohin sie zoomen sollen. Wir müssen nicht raten: Das Skript, das
die Aufnahme steuert, löst den Klick selbst aus und **kennt Zeit und Ort**. Es
gibt beides hier als ``--beat SEKUNDE:X:Y`` herein, und daraus entsteht:

* ein **Zoom** auf die Stelle — er beginnt kurz VOR dem Klick (Erwartung),
  hält, und fährt danach wieder heraus; jede Fahrt mit weicher Kurve
  (Smoothstep), damit nichts springt,
* der **Tipp** als orange Scheibe mit fünf wachsenden Ringen, gezeichnet im
  gezoomten Bild, also immer scharf.

Warum ein eigenes Skript und nicht ffmpeg allein: ``crop`` wertet Breite und
Höhe nur beim Start aus, ``zoompan`` rechnet in Bildnummern mit einer
Ausdrucks-Sprache, in der drei Beats unlesbar werden. Hier ist es eine
Funktion mit einem Test (``tests/test_highlight_clip.py``).

Aufruf::

    .venv/bin/python scripts/highlight_clip.py roh.mp4 fertig.mp4 \\
        --beat 2.2:1068:2037            # Sekunde 2,2, Klick bei (1068, 2037)
        [--zoom 1.8] [--hold 2.4]       # Faktor, Haltedauer nach dem Klick

Koordinaten in Pixeln des ROHEN Videos. Mehrere ``--beat`` sind erlaubt.
Bild für Bild über zwei ffmpeg-Röhren (rgb24), Pillow schneidet und
skaliert — 300 Bilder eines Telefon-Clips brauchen wenige Sekunden.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

ORANGE = (255, 107, 44)


@dataclass(frozen=True)
class Beat:
    """Ein Klick: wann und wo (Pixel des Rohvideos).

    ``tap=False`` ist ein Blick statt eines Klicks: Der Zoom fährt hin, aber
    es wird keine Tipp-Markierung gezeichnet — für eine Erklärung, die schon
    beim Überfahren aufgeht (ein Klick schlösse sie wieder).
    """
    t: float
    x: float
    y: float
    tap: bool = True


@dataclass(frozen=True)
class Timing:
    zoom: float = 1.8      # Faktor im Halt
    lead: float = 0.55     # Zoom beginnt so viele Sekunden VOR dem Klick
    hold: float = 2.4      # Halt nach dem Klick, voll gezoomt
    release: float = 0.7   # Fahrt zurück


def smoothstep(p: float) -> float:
    """0→1 mit weichem Anfang und Ende. Linear sähe man den Ruck an beiden Enden."""
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def zoom_state(t: float, beats: list[Beat], size: tuple[int, int],
               timing: Timing = Timing()) -> tuple[float, float, float]:
    """``(zoom, cx, cy)`` zum Zeitpunkt ``t``.

    Außerhalb aller Beats 1 und Bildmitte. Rund um einen Beat: Anfahrt (vor dem
    Klick), Halt, Rückfahrt — und die Mitte wandert mit derselben Kurve von der
    Bildmitte zum Klickpunkt und zurück. Überlappen sich zwei Beats, gewinnt
    der spätere; das ist bei einem Tipp alle paar Sekunden nie der Fall.
    """
    w, h = size
    mitte = (w / 2, h / 2)
    z, cx, cy = 1.0, mitte[0], mitte[1]
    for b in beats:
        start = b.t - timing.lead
        ende_halt = b.t + timing.hold
        ende = ende_halt + timing.release
        if start <= t < b.t:
            p = smoothstep((t - start) / timing.lead)
        elif b.t <= t < ende_halt:
            p = 1.0
        elif ende_halt <= t < ende:
            p = 1.0 - smoothstep((t - ende_halt) / timing.release)
        else:
            continue
        z = 1.0 + (timing.zoom - 1.0) * p
        cx = mitte[0] + (b.x - mitte[0]) * p
        cy = mitte[1] + (b.y - mitte[1]) * p
    return z, cx, cy


def crop_box(z: float, cx: float, cy: float, size: tuple[int, int]) -> tuple[float, float, float, float]:
    """Der Ausschnitt ``(x, y, w, h)`` — an den Bildrand geklemmt.

    Ein Klick nahe am Rand darf den Ausschnitt nicht aus dem Bild schieben:
    Dann rückt er eben nicht in die Mitte, sondern so weit wie es geht.
    """
    w, h = size
    bw, bh = w / z, h / z
    x = min(max(cx - bw / 2, 0.0), w - bw)
    y = min(max(cy - bh / 2, 0.0), h - bh)
    return x, y, bw, bh


def draw_touch(bild: Image.Image, ox: float, oy: float, seit: float, scale: float) -> None:
    """Der Tipp: gefüllte Scheibe, darüber ein Ring, der wächst und verblasst.

    ``seit`` sind Sekunden seit dem Klick (auch leicht negativ: die Scheibe
    erscheint einen Wimpernschlag vorher). ``scale`` ist der Zoom, damit die
    Markierung im gezoomten Bild nicht riesig wird.
    """
    z = ImageDraw.Draw(bild, "RGBA")
    if -0.10 <= seit <= 0.42:
        r = 46 * scale ** 0.5
        z.ellipse((ox - r, oy - r, ox + r, oy + r), fill=(*ORANGE, 95), outline=(*ORANGE, 225), width=max(3, int(5 * scale ** 0.5)))
    if 0.0 <= seit <= 0.55:
        p = seit / 0.55
        r = (58 + 150 * p) * scale ** 0.5
        alpha = int(235 * (1 - p) ** 1.4)
        z.ellipse((ox - r, oy - r, ox + r, oy + r), outline=(*ORANGE, alpha), width=max(2, int((11 - 6 * p) * scale ** 0.5)))


def probe(pfad: Path) -> tuple[int, int, float]:
    aus = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate", "-of", "json", str(pfad)],
        capture_output=True, text=True, check=True).stdout
    s = json.loads(aus)["streams"][0]
    zaehler, nenner = s["r_frame_rate"].split("/")
    return int(s["width"]), int(s["height"]), float(zaehler) / float(nenner)


def polish(quelle: Path, ziel: Path, beats: list[Beat], timing: Timing,
           touch: bool = True, crf: int = 26) -> int:
    """Rohclip → polierter Clip. Gibt die Zahl der Bilder zurück."""
    w, h, fps = probe(quelle)
    groesse = (w, h)
    bytes_je_bild = w * h * 3

    lesen = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(quelle), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    schreiben = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{w}x{h}", "-r", f"{fps:.6f}", "-i", "-",
         "-c:v", "libx264", "-profile:v", "main", "-pix_fmt", "yuv420p",
         "-crf", str(crf), "-movflags", "+faststart", "-an", str(ziel)],
        stdin=subprocess.PIPE)
    assert lesen.stdout is not None and schreiben.stdin is not None

    n = 0
    while True:
        roh = lesen.stdout.read(bytes_je_bild)
        if len(roh) < bytes_je_bild:
            break
        t = n / fps
        z, cx, cy = zoom_state(t, beats, groesse, timing)
        bild = Image.frombytes("RGB", groesse, roh)
        if z > 1.0001:
            x, y, bw, bh = crop_box(z, cx, cy, groesse)
            # LANCZOS beim Vergrößern hält Schrift lesbar; BILINEAR franst.
            bild = bild.crop((int(x), int(y), int(x + bw), int(y + bh))).resize(groesse, Image.LANCZOS)
        else:
            x, y = 0.0, 0.0
        if touch:
            for b in beats:
                seit = t - b.t
                if b.tap and -0.10 <= seit <= 0.55:
                    # Klickpunkt in Ausgabe-Koordinaten: durch den Ausschnitt gerechnet.
                    draw_touch(bild, (b.x - x) * z, (b.y - y) * z, seit, z)
        schreiben.stdin.write(bild.tobytes())
        n += 1

    schreiben.stdin.close()
    schreiben.wait()
    lesen.wait()
    if schreiben.returncode:
        raise RuntimeError("ffmpeg konnte nicht schreiben")
    return n


def _beat(text: str) -> Beat:
    try:
        t, x, y, *rest = text.split(":")
        if rest and rest != ["look"]:
            raise ValueError(text)
        return Beat(float(t), float(x), float(y), tap=not rest)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--beat erwartet SEKUNDE:X:Y[:look], nicht {text!r}") from e


def main() -> int:
    p = argparse.ArgumentParser(description="Highlight-Clip polieren: Zoom auf den Klick, sichtbarer Tipp")
    p.add_argument("quelle", type=Path)
    p.add_argument("ziel", type=Path)
    p.add_argument("--beat", type=_beat, action="append", required=True,
                   help="SEKUNDE:X:Y — Zeitpunkt und Klickpunkt in Rohpixeln; mehrfach erlaubt. "
                        ":look dahinter zoomt nur, ohne Tipp-Markierung")
    p.add_argument("--zoom", type=float, default=Timing.zoom, help="Faktor im Halt (Vorgabe 1,8)")
    p.add_argument("--hold", type=float, default=Timing.hold, help="Halt nach dem Klick in Sekunden")
    p.add_argument("--lead", type=float, default=Timing.lead, help="Anfahrt vor dem Klick in Sekunden")
    p.add_argument("--release", type=float, default=Timing.release, help="Rückfahrt in Sekunden")
    p.add_argument("--ohne-tipp", action="store_true", help="keine Tipp-Markierung zeichnen")
    args = p.parse_args()

    timing = Timing(zoom=args.zoom, lead=args.lead, hold=args.hold, release=args.release)
    n = polish(args.quelle, args.ziel, args.beat, timing, touch=not args.ohne_tipp)
    print(f"{n} Bilder → {args.ziel} ({args.ziel.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
