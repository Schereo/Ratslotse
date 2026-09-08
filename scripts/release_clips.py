#!/usr/bin/env python3
"""Die Clips für „Neu bei Ratslotse" — aus Drehbüchern, für jede Ausgabe neu.

Jedes Highlight der Karte (``kern/releases.py``) bringt einen kleinen Clip
mit, in dem man sieht, wie man das Feature bedient: Der Zeiger fährt hin, der
Klick ist markiert, das Bild zoomt auf die Stelle. Dieses Skript macht aus
einem Drehbuch den fertigen Clip samt Standbild — und legt beides dort ab, wo
die Registry es erwartet (``web/frontend/public/neuigkeiten/<version>/``).

Drei Aufrufe, in dieser Reihenfolge beim Release::

    scripts/release_clips.py skeleton 2.3.0                 # Drehbuch-Gerüst aus der Registry
    scripts/release_clips.py web 2.3.0 [--only teilen]      # Browser-Clips aufnehmen + schneiden
    scripts/release_clips.py ios 2.3.0 teilen --segment a.mov:X:Y …   # iPhone-Aufnahmen zusammensetzen
    scripts/release_clips.py check 2.3.0                    # jedes Video hat ein Drehbuch, jedes Drehbuch ein Video

**Browser:** ``web/frontend/scripts/release-clip.mjs`` spielt das Drehbuch aus
``web/frontend/release-clips/<version>.mjs`` in Chrome ab (Playwright,
sichtbarer Zeiger) und liefert die Bildwechsel des Screencasts mit Uhrzeit
sowie je Klick Uhrzeit und Ort. Hier werden die Bilder ab ``begin()`` zu
einem Video mit 30 fps gelegt, von ``highlight_clip.py`` gezoomt und als
MP4 + WebP-Standbild abgelegt. Voraussetzung: Frontend und
Backend laufen lokal mit echten Daten (``scripts/dev.py start``,
``scripts/lokale_daten.py``, ``scripts/saat_konten.py``).

**iPhone:** Der Simulator kennt keinen Zeiger und ``simctl recordVideo`` keine
Tipps — je Beat wird EINE Aufnahme gemacht (Tipp auslösen, drei Sekunden
laufen lassen). Dieses Skript findet in jeder den ersten Bildwechsel (die
Reaktion auf den Tipp), schneidet darum herum und legt die Stücke aneinander;
die Nähte liegen auf identischen Standbildern. Der Tippunkt kommt als Rohpixel
mit (``DATEI:X:Y``). Das Rezept dazu steht in REZEPTE.md („Release fahren").

Warum Drehbücher als Code und nicht eine Aufnahme-App: Das Drehbuch löst den
Klick selbst aus und **kennt** Zeit und Ort. Eine App müsste beides aus der
Mausbewegung raten — und beim nächsten Release ginge alles von vorn los.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kern import releases  # noqa: E402
from scripts.highlight_clip import Beat, Timing, polish  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web" / "frontend"
STORYBOARDS = FRONTEND / "release-clips"
MEDIA = FRONTEND / "public" / "neuigkeiten"
RECORDER = FRONTEND / "scripts" / "release-clip.mjs"

#: Zoom-Takt je Oberfläche. Der Halt ist kurz, weil die Pointe (Toast,
#: Teilen-Blatt) meist AUSSERHALB des Ausschnitts liegt und erst beim
#: Zurückfahren sichtbar wird; die Rückfahrt ist deshalb die längere Phase.
WEB_TIMING = Timing(zoom=1.6, lead=0.55, hold=0.5, release=0.9)
IOS_TIMING = Timing(zoom=1.5, lead=0.55, hold=0.6, release=0.9)
WEB_WIDTH = 1400        # Ausgabebreite der Browser-Clips
IOS_HEIGHT = 1400       # Ausgabehöhe der iPhone-Clips (volles Telefon)
TAIL = 2.5              # eingefrorener Schluss in Sekunden
REACTION = 0.25         # der Tipp liegt so weit VOR dem ersten Bildwechsel
BEFORE, AFTER = 1.5, 2.5  # Schnittfenster um den Bildwechsel eines iPhone-Beats
CHANGE_THRESHOLD = 6.0  # mittlere Graustufen-Differenz, ab der ein Bild „anders" ist

#: Ein Drehbuch-Eintrag steht in ``release-clips/<version>.mjs`` als Schlüssel
#: mit zwei Leerzeichen Einzug: ``  teilen: {``. Der Name ist der Dateistamm
#: des Mediums in der Registry.
STORYBOARD_KEY = re.compile(r"^  ([\w-]+):\s*\{", re.MULTILINE)


# --------------------------------------------------------------------------
# Reine Funktionen (getestet in tests/test_release_clips.py)
# --------------------------------------------------------------------------

def storyboard_names(version: str) -> list[str]:
    """Die Namen der Drehbücher einer Ausgabe — leer, wenn es die Datei nicht gibt."""
    datei = STORYBOARDS / f"{version}.mjs"
    if not datei.exists():
        return []
    return STORYBOARD_KEY.findall(datei.read_text(encoding="utf-8"))


def web_video_names(release: releases.Release) -> list[str]:
    """Die Dateistämme der Browser-Clips eines Releases — das sind die Namen,
    die ein Drehbuch tragen muss."""
    return [Path(h.media.src).stem for h in release.highlights
            if h.media is not None and h.media.kind == "video"]


def clip_start(frames: list[tuple[float, Path]], begin: float | None) -> float:
    """Die Uhrzeit, ab der der Clip zählt: ``begin()`` — oder das erste Bild."""
    return begin if begin is not None else frames[0][0]


def frame_plan(frames: list[tuple[float, Path]], begin: float | None, end: float) -> list[tuple[Path, float]]:
    """Welches Bild wie lange steht — ``(Datei, Sekunden)``, ab ``begin``.

    Der Screencast liefert nur Bildwechsel mit Uhrzeit. Das Bild, das bei
    ``begin`` gerade zu sehen war, ist das letzte davor; es eröffnet den
    Clip. Jedes Bild steht bis zum nächsten, das letzte bis ``end``.
    """
    start = clip_start(frames, begin)
    davor = [f for f in frames if f[0] <= start]
    # Bilder nach ``end`` (der Recorder sammelt noch 300 ms nach) bleiben draußen.
    danach = [f for f in frames if start < f[0] < end]
    reihe = ([davor[-1]] if davor else []) + danach
    plan: list[tuple[Path, float]] = []
    for i, (t, datei) in enumerate(reihe):
        naechste = min(reihe[i + 1][0], end) if i + 1 < len(reihe) else end
        dauer = naechste - max(t, start)
        if dauer > 0:
            plan.append((datei, dauer))
    return plan


def beat_times(start: float, beats: Iterable[float]) -> list[float]:
    """Uhrzeiten der Klicks → Sekunden im Clip."""
    return [t - start for t in beats]


def first_change(frames: Iterable[Image.Image], threshold: float = CHANGE_THRESHOLD) -> int | None:
    """Index des ersten Bildes, das sich vom ERSTEN deutlich unterscheidet.

    Der Vergleich geht immer gegen das Ausgangsbild, nicht gegen den
    Vorgänger: Ein langsam aufblendendes Teilen-Blatt ändert je Bild nur
    wenig, gegen den Anfang aber bald genug.
    """
    basis: Image.Image | None = None
    for i, bild in enumerate(frames):
        grau = bild.convert("L")
        if basis is None:
            basis = grau
            continue
        mittel = ImageStat.Stat(ImageChops.difference(grau, basis)).mean[0]
        if mittel > threshold:
            return i
    return None


# --------------------------------------------------------------------------
# ffmpeg-Handgriffe
# --------------------------------------------------------------------------

def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def duration(pfad: Path) -> float:
    aus = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(pfad)],
        capture_output=True, text=True, check=True).stdout
    return float(aus.strip())


def normalize(quelle: Path, ziel: Path, start: float = 0.0, length: float | None = None,
              crop: tuple[int, int] | None = None) -> None:
    """Auf feste 30 fps, verlustarm, optional zugeschnitten (Zeit und Bild).

    Sowohl Playwright (webm) als auch ``simctl recordVideo`` liefern Bilder
    mit krummen Zeitstempeln — der Simulator schreibt sogar nur bei
    Bildwechseln. Erst auf 30 fps ist eine Sekunde eine Sekunde. ``crop``
    nimmt die obere linke Ecke in der genannten Größe; die Klickpunkte
    bleiben dabei gültig.
    """
    zeit = ["-ss", f"{start:.3f}"] if start > 0 else []
    laenge = ["-t", f"{length:.3f}"] if length is not None else []
    filter_ = "fps=30" + (f",crop={crop[0]}:{crop[1]}:0:0" if crop else "")
    ffmpeg(*zeit, "-i", str(quelle), *laenge, "-vf", filter_,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-an", str(ziel))


def change_time(video: Path, threshold: float = CHANGE_THRESHOLD) -> float | None:
    """Sekunde des ersten Bildwechsels in einem (normalisierten) Video."""
    with tempfile.TemporaryDirectory() as tmp:
        ffmpeg("-i", str(video), "-vf", "fps=10,scale=120:-1", f"{tmp}/f%04d.png")
        bilder = sorted(Path(tmp).glob("f*.png"))
        index = first_change((Image.open(b) for b in bilder), threshold)
    return None if index is None else index / 10


def pad_to(video: Path, seconds: float) -> None:
    """Das letzte Bild stehen lassen, bis ``seconds`` voll sind.

    ``simctl recordVideo`` schreibt nur bei Bildwechseln: Nach dem Aufklappen
    einer Karte endet die Aufnahme, egal wie lange man wartet — das Stück
    wäre kürzer als sein Fenster, und die Pointe bliebe einen Wimpernschlag.
    """
    fehlt = seconds - duration(video)
    if fehlt <= 0.05:
        return
    voll = video.with_name(video.stem + "-voll.mp4")
    ffmpeg("-i", str(video), "-vf", f"tpad=stop_mode=clone:stop_duration={fehlt:.3f},fps=30",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-an", str(voll))
    voll.replace(video)


def motion_spans(video: Path, threshold: float = 1.5, gap: float = 0.5) -> list[tuple[float, float]]:
    """Wann bewegt sich etwas? ``[(von, bis), …]`` in Sekunden.

    Bild gegen Vorgänger, zehnmal je Sekunde; Lücken bis ``gap`` werden
    überbrückt. Für ein Stück ohne Tipp (Blättern) zählt nur das: Die
    Simulator-Aufnahme dehnt stehende Zeit auf ein Vielfaches, und zwischen
    zwei Wischern wartete das Werkzeug ohnehin Sekunden.
    """
    with tempfile.TemporaryDirectory() as tmp:
        ffmpeg("-i", str(video), "-vf", "fps=10,scale=120:-1", f"{tmp}/f%04d.png")
        vorher: Image.Image | None = None
        spans: list[list[float]] = []
        for i, datei in enumerate(sorted(Path(tmp).glob("f*.png"))):
            grau = Image.open(datei).convert("L")
            if vorher is not None and ImageStat.Stat(ImageChops.difference(grau, vorher)).mean[0] > threshold:
                t = i / 10
                if spans and t - spans[-1][1] <= gap:
                    spans[-1][1] = t
                else:
                    spans.append([t, t])
            vorher = grau
    return [(a, b) for a, b in spans]


def concat_with_tail(teile: list[Path], ziel: Path, tail: float = TAIL) -> None:
    """Stücke aneinanderlegen und das letzte Bild einfrieren."""
    eingaben = [arg for t in teile for arg in ("-i", str(t))]
    kette = "".join(f"[{i}:v]" for i in range(len(teile)))
    kette += (f"concat=n={len(teile)}:v=1:a=0[z];"
              f"[z]tpad=stop_mode=clone:stop_duration={tail},fps=30[out]")
    ffmpeg(*eingaben, "-filter_complex", kette, "-map", "[out]",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-an", str(ziel))


def finish(roh: Path, beats: list[Beat], timing: Timing, mp4: Path, webp: Path,
           *, width: int | None = None, height: int | None = None) -> int:
    """Zoom + Tipp, dann auf Zielgröße, dann das Standbild. Gibt die Bildzahl zurück."""
    mp4.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        voll = Path(tmp) / "voll.mp4"
        n = polish(roh, voll, beats, timing, crf=18)
        skala = f"scale={width}:-2" if width else f"scale=-2:{height}"
        ffmpeg("-i", str(voll), "-vf", skala,
               "-c:v", "libx264", "-profile:v", "main", "-pix_fmt", "yuv420p",
               "-crf", "26", "-movflags", "+faststart", "-an", str(mp4))
        standbild = Path(tmp) / "poster.png"
        ffmpeg("-i", str(mp4), "-frames:v", "1", str(standbild))
        Image.open(standbild).convert("RGB").save(webp, "WEBP", quality=82, method=6)
    return n


# --------------------------------------------------------------------------
# Browser
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Recording:
    """Was der Recorder abliefert: Bilder mit Uhrzeit, Marken mit derselben Uhr."""
    width: int
    height: int
    frames: list[tuple[float, Path]]                 # (Uhrzeit des Bildwechsels, Datei)
    begin: float | None
    end: float
    beats: list[tuple[float, float, float, bool]]    # (Uhrzeit, x, y, Tipp?)


def record_web(version: str, name: str, base: str, out: Path) -> Recording:
    """Das Drehbuch in Chrome abspielen; der Recorder schreibt ein Manifest."""
    lauf = subprocess.run(
        ["node", str(RECORDER), version, name, "--out", str(out), "--base", base],
        cwd=FRONTEND, capture_output=True, text=True)
    if lauf.returncode:
        raise SystemExit(f"Aufnahme „{name}“ gescheitert:\n{lauf.stderr.strip()}")
    zeile = lauf.stdout.strip().splitlines()[-1]
    daten = json.loads(Path(json.loads(zeile)["manifest"]).read_text(encoding="utf-8"))
    if not daten["frames"]:
        raise SystemExit(f"Aufnahme „{name}“: kein einziges Bild — läuft das Frontend unter {base}?")
    return Recording(
        width=int(daten["width"]), height=int(daten["height"]),
        frames=[(float(f["t"]), Path(f["file"])) for f in daten["frames"]],
        begin=daten.get("begin"), end=float(daten["end"]),
        beats=[(float(b["t"]), float(b["x"]), float(b["y"]), bool(b.get("tap", True)))
               for b in daten["beats"]],
    )


def assemble(plan: list[tuple[Path, float]], ziel: Path, crop: tuple[int, int] | None = None) -> None:
    """Aus Standbildern mit Dauer ein Video mit 30 fps — über ffmpegs
    concat-Demuxer, der je Bild eine ``duration`` versteht."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as liste:
        liste.write("ffconcat version 1.0\n")
        for datei, dauer in plan:
            liste.write(f"file '{datei}'\nduration {dauer:.4f}\n")
        # Das letzte Bild noch einmal nennen, sonst gilt seine Dauer nicht.
        liste.write(f"file '{plan[-1][0]}'\n")
        pfad = liste.name
    filter_ = "fps=30" + (f",crop={crop[0]}:{crop[1]}:0:0" if crop else "")
    ffmpeg("-f", "concat", "-safe", "0", "-i", pfad, "-vf", filter_,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-an", str(ziel))
    Path(pfad).unlink(missing_ok=True)


def cmd_web(args: argparse.Namespace) -> int:
    version: str = args.version
    release = releases.get(version)
    if release is None:
        print(f"Kein Release {version} in kern/releases.py.", file=sys.stderr)
        return 2
    namen = storyboard_names(version)
    if not namen:
        print(f"Kein Drehbuch unter {STORYBOARDS / (version + '.mjs')} — "
              f"`scripts/release_clips.py skeleton {version}` legt eines an.", file=sys.stderr)
        return 2
    if args.only:
        fehlend = [n for n in args.only if n not in namen]
        if fehlend:
            print(f"Unbekannte Drehbücher: {', '.join(fehlend)} (vorhanden: {', '.join(namen)})",
                  file=sys.stderr)
            return 2
        namen = [n for n in namen if n in args.only]

    ziel = MEDIA / version
    for name in namen:
        print(f"● {name} … aufnehmen", flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            aufnahme = record_web(version, name, args.base, Path(tmp))
            start = clip_start(aufnahme.frames, aufnahme.begin)
            plan = frame_plan(aufnahme.frames, aufnahme.begin, aufnahme.end)
            roh = Path(tmp) / "roh.mp4"
            # Oben 16:9 — unten steht bei 980 px die Tab-Leiste der App.
            assemble(plan, roh, crop=(aufnahme.width, aufnahme.width * 9 // 16))
            zeiten = beat_times(start, [t for t, _, _, _ in aufnahme.beats])
            beats = [Beat(t, x, y, tap) for t, (_, x, y, tap) in zip(zeiten, aufnahme.beats)]
            n = finish(roh, beats, WEB_TIMING, ziel / f"{name}.mp4", ziel / f"{name}.webp",
                       width=WEB_WIDTH)
        groesse = (ziel / f"{name}.mp4").stat().st_size // 1024
        takte = ", ".join(f"{b.t:.1f}s" for b in beats) or "keine Beats"
        print(f"  ✓ {name}.mp4 ({n} Bilder, {groesse} KB, Beats: {takte}) + {name}.webp")
    return 0


# --------------------------------------------------------------------------
# iPhone
# --------------------------------------------------------------------------

def _segment(text: str) -> tuple[Path, float | None, float | None]:
    """``DATEI:X:Y`` ist ein Tipp; ``DATEI`` allein ein Stück ohne Tipp (Blättern)."""
    if text.endswith((".mov", ".mp4")):
        return Path(text), None, None
    try:
        datei, x, y = text.rsplit(":", 2)
        return Path(datei), float(x), float(y)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--segment erwartet DATEI:X:Y oder DATEI, nicht {text!r}") from e


def _point(text: str) -> tuple[float, float]:
    try:
        x, y = text.split(":")
        return float(x), float(y)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"--focus erwartet X:Y, nicht {text!r}") from e


def cmd_ios(args: argparse.Namespace) -> int:
    version: str = args.version
    if releases.get(version) is None:
        print(f"Kein Release {version} in kern/releases.py.", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        stuecke: list[Path] = []
        beats: list[Beat] = []
        offset = 0.0
        for i, (datei, x, y) in enumerate(args.segment):
            norm = Path(tmp) / f"norm{i}.mp4"
            normalize(datei, norm)
            wechsel = change_time(norm)
            if wechsel is None:
                print(f"{datei}: kein Bildwechsel gefunden — hat der Tipp etwas ausgelöst?", file=sys.stderr)
                return 1
            teil = Path(tmp) / f"teil{i}.mp4"
            if x is None or y is None:
                # Ohne Tipp (Blättern): nur die Bewegung, jede Spanne mit
                # etwas Luft davor und danach. Was dazwischen steht, ist
                # dasselbe Standbild — der Schnitt ist unsichtbar.
                for j, (von, bis) in enumerate(motion_spans(norm)):
                    stueck = Path(tmp) / f"teil{i}-{j}.mp4"
                    anfang = max(0.0, von - 0.3)
                    normalize(norm, stueck, start=anfang, length=(bis - anfang) + 0.6)
                    stuecke.append(stueck)
                    offset += duration(stueck)
                continue
            else:
                start = max(0.0, wechsel - BEFORE)
                normalize(norm, teil, start=start, length=(wechsel - start) + AFTER)
                pad_to(teil, (wechsel - start) + AFTER)
                beats.append(Beat(offset + (wechsel - start) - REACTION, x, y))
            stuecke.append(teil)
            offset += duration(teil)
        tail = max(args.tail, 2.0 if args.focus else 0.0)
        if args.focus:
            # Der Schluss-Blick: Zoom auf die Stelle, um die es am Ende geht
            # (etwa „Läuft gerade“ an einer Zeile) — Anfahrt im letzten Bild,
            # Halt und Rückfahrt im eingefrorenen Schluss.
            beats.append(Beat(offset - 0.3, args.focus[0], args.focus[1], tap=False))
        roh = Path(tmp) / "roh.mp4"
        concat_with_tail(stuecke, roh, tail)
        ziel = MEDIA / version
        n = finish(roh, beats, IOS_TIMING, ziel / f"{args.name}-ios.mp4", ziel / f"{args.name}-ios.webp",
                   height=IOS_HEIGHT)
    groesse = (ziel / f"{args.name}-ios.mp4").stat().st_size // 1024
    takte = ", ".join(f"{b.t:.1f}s" for b in beats)
    print(f"✓ {args.name}-ios.mp4 ({n} Bilder, {groesse} KB, Beats: {takte}) + {args.name}-ios.webp")
    return 0


# --------------------------------------------------------------------------
# Gerüst und Prüfung
# --------------------------------------------------------------------------

def _slug(highlight: releases.Highlight) -> str:
    if highlight.media is not None:
        return Path(highlight.media.src).stem
    return re.sub(r"[^a-z0-9]+", "-", highlight.title.lower()).strip("-")[:24]


def skeleton(release: releases.Release) -> str:
    """Ein Drehbuch-Gerüst: je Highlight ein Eintrag mit Titel und Ziel-Pfad."""
    teile = [
        f"// Drehbücher für die Clips von Ratslotse {release.version} — eines je Highlight\n"
        f"// aus kern/releases.py. Aufnahme: python scripts/release_clips.py web {release.version}\n"
        "//\n"
        "// Ein Drehbuch bekommt die Bühne (`stage`) und spielt darauf eine kurze\n"
        "// Szene: erst Aufbau (Seite öffnen, Zustand herstellen), dann `begin()`,\n"
        "// dann die Klicks. Alles vor `begin()` wird weggeschnitten; jeder `click()`\n"
        "// wird zum Zoom-Beat. Was `stage` kann, steht in scripts/release-clip.mjs.\n"
        "export default {\n"
    ]
    for h in release.highlights:
        if h.only == releases.NUR_NATIVE:
            continue
        teile.append(
            f"  {_slug(h)}: {{\n"
            f"    // {h.title}\n"
            f"    async run({{ goto, begin, click, pause }}) {{\n"
            f"      await goto({h.url!r});\n"
            f"      await pause(0.8);\n"
            f"      await begin();\n"
            f"      await pause(0.5);\n"
            f"      // await click('button:has-text(\"…\")');\n"
            f"      await pause(2.5);\n"
            f"    }},\n"
            f"  }},\n"
        )
    teile.append("};\n")
    return "".join(teile)


def cmd_skeleton(args: argparse.Namespace) -> int:
    release = releases.get(args.version)
    if release is None:
        print(f"Kein Release {args.version} in kern/releases.py — erst den Eintrag anlegen "
              f"(`scripts/changelog_schnitt.py {args.version} --highlights` schlägt ihn vor).",
              file=sys.stderr)
        return 2
    datei = STORYBOARDS / f"{args.version}.mjs"
    if datei.exists() and not args.force:
        print(f"{datei} gibt es schon (--force überschreibt).", file=sys.stderr)
        return 1
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(skeleton(release), encoding="utf-8")
    print(f"✓ {datei.relative_to(ROOT)} — {len(storyboard_names(args.version))} Drehbuch-Einträge")
    return 0


def missing_and_stale(release: releases.Release) -> tuple[list[str], list[str]]:
    """Clips ohne Drehbuch und Drehbücher ohne Clip — beide Richtungen."""
    videos = set(web_video_names(release))
    buecher = set(storyboard_names(release.version))
    return sorted(videos - buecher), sorted(buecher - videos)


def cmd_check(args: argparse.Namespace) -> int:
    release = releases.get(args.version)
    if release is None:
        print(f"Kein Release {args.version} in kern/releases.py.", file=sys.stderr)
        return 2
    fehlend, verwaist = missing_and_stale(release)
    for name in fehlend:
        print(f"✗ {name}.mp4 steht in der Registry, hat aber kein Drehbuch in "
              f"release-clips/{release.version}.mjs")
    for name in verwaist:
        print(f"✗ Drehbuch „{name}“ hat kein Video in kern/releases.py ({release.version})")
    if not fehlend and not verwaist:
        print(f"✓ {release.version}: {len(web_video_names(release))} Clips, jeder mit Drehbuch")
    return 1 if (fehlend or verwaist) else 0


def main() -> int:
    if shutil.which("ffmpeg") is None:
        print("ffmpeg fehlt (brew install ffmpeg).", file=sys.stderr)
        return 2
    p = argparse.ArgumentParser(description="Clips für „Neu bei Ratslotse“ aufnehmen und schneiden")
    sub = p.add_subparsers(dest="befehl", required=True)

    w = sub.add_parser("web", help="Browser-Clips nach Drehbuch aufnehmen und ablegen")
    w.add_argument("version")
    w.add_argument("--only", nargs="+", metavar="NAME", help="nur diese Drehbücher")
    w.add_argument("--base", default="http://localhost:3000", help="laufendes Frontend")
    w.set_defaults(func=cmd_web)

    i = sub.add_parser("ios", help="iPhone-Aufnahmen (eine je Beat) zusammensetzen")
    i.add_argument("version")
    i.add_argument("name", help="Dateistamm des Highlights, z. B. teilen → teilen-ios.mp4")
    i.add_argument("--segment", type=_segment, action="append", required=True, metavar="DATEI[:X:Y]",
                   help="eine Aufnahme je Stück, in Reihenfolge: mit Tippunkt in Rohpixeln (Beat) "
                        "oder ohne (Blättern); mehrfach")
    i.add_argument("--focus", type=_point, metavar="X:Y",
                   help="Schluss-Blick: Zoom ohne Tipp auf diese Stelle im letzten Bild")
    i.add_argument("--tail", type=float, default=TAIL, help="eingefrorener Schluss in Sekunden")
    i.set_defaults(func=cmd_ios)

    s = sub.add_parser("skeleton", help="Drehbuch-Gerüst aus kern/releases.py anlegen")
    s.add_argument("version")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_skeleton)

    c = sub.add_parser("check", help="Registry und Drehbücher gegeneinander halten")
    c.add_argument("version")
    c.set_defaults(func=cmd_check)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
