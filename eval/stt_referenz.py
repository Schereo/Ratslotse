#!/usr/bin/env python3
"""Referenztext für die Transkriptions-Eval aus YouTube-Untertiteln schneiden.

    python eval/stt_referenz.py <ksinr>

``eval/run_stt.py`` braucht je aufbewahrtem Stück (``council/stt_retain.py``,
``~/.cache/ratslotse/stt/<ksinr>/``) eine unabhängige Referenz — unabhängig
heißt: nicht von demselben Modell, das auch im Betrieb transkribiert.
YouTubes Auto-Untertitel derselben Sitzung (``eval/transkripte.py``) sind
diese zweite Quelle; hier werden sie auf die 30-Sekunden-Fenster der
aufgehobenen Stücke geschnitten und als ``<name>.txt`` neben die Stücke
gelegt — genau die Datei, die ``eval/run_stt.py`` als Referenz liest.

**Der Zeitversatz.** Der Livestream-Mitschnitt beginnt eigenständig
(``LEAD_MINUTES`` vor der angesetzten Zeit, s.
``scripts/record_council_livestream.py``), das YouTube-Video hat seinen
eigenen Nullpunkt — beide Uhren laufen synchron, aber mit unbekanntem
Abstand. Wie ``eval/run_live_tracker.py`` es für die Live-Verfolgung tut,
liefert ein Tagesordnungspunkt-Aufruf den Anker: Derselbe Aufruf
(„Tagesordnungspunkt 6.1" o. ä.) taucht in beiden Transkripten auf, der
Zeitversatz ist die Differenz ihrer Zeitstempel. Als Textquelle auf der
Stream-Seite dient, was der PRODUKTIONSWEG selbst transkribiert hat
(``<name>.chunks.txt`` / ``<name>.gladia.txt``, von ``stt_retain`` neben die
Stücke gelegt) — ungenau, aber für die Synchronisation reicht die grobe
Zeitmarke. Kommt kein gemeinsamer Aufruf vor (zu wenige aufgehobene Stücke,
oder keiner trifft eine Aufrufstelle), verlangt das Werkzeug ``--versatz``
von Hand.

**Bewusst grob.** Die Referenz ist für eine grobe Wort-F1 gedacht
(``eval/run_stt.py``), keine sekundengenaue Wortfolge-Fehlerrate — eine
Verschiebung von 1-2 Sekunden an der Stückgrenze fällt dort nicht ins
Gewicht.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

#: Was einen Tagesordnungspunkt-Aufruf markiert — dieselbe Absicht wie
#: ``stream_stt.TRIGGER_RE``, hier aber auf die NUMMER zugespitzt, die als
#: Anker zwischen beiden Transkripten dient.
TOP_RE = re.compile(
    r"Tagesordnungspunkt\s+(\d+(?:\.\d+)?)|\bTOP\s+(\d+(?:\.\d+)?)"
    r"|\bPunkt\s+(\d+(?:\.\d+)?)", re.I)

#: Die beiden Wege, deren Vergleichstext ``stt_retain`` neben ein Stück legt.
WEGE = ("chunks", "gladia")


def top_aufrufe(segmente: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """[(Sekunde, TOP-Nummer)] — jede Fundstelle in den Segmenten."""
    out: list[tuple[float, str]] = []
    for t, text in segmente:
        for m in TOP_RE.finditer(text or ""):
            nr = next((g for g in m.groups() if g), None)
            if nr:
                out.append((float(t), nr))
    return out


def schaetze_versatz(stream_aufrufe: list[tuple[float, str]],
                     video_aufrufe: list[tuple[float, str]]) -> float | None:
    """Zeitversatz (Video minus Stream) über gemeinsame TOP-Aufrufe — der
    MEDIAN mehrerer Treffer, falls es welche gibt, damit ein einzelner
    Zufallstreffer (dieselbe Nummer an zwei Stellen) nicht täuscht."""
    erster_video: dict[str, float] = {}
    for t, nr in video_aufrufe:
        erster_video.setdefault(nr, t)
    diffs = sorted(erster_video[nr] - t for t, nr in stream_aufrufe if nr in erster_video)
    if not diffs:
        return None
    return diffs[len(diffs) // 2]


def fenster_text(segmente: list[tuple[float, str]], von: float, bis: float) -> str:
    """Alle Segmente, deren Start im Fenster ``[von, bis)`` liegt, aneinander."""
    return " ".join(text.strip() for t, text in segmente if von <= t < bis and text.strip())


def gewaehlte_stuecke(ordner: Path) -> list[tuple[int, Path, str]]:
    """[(Index, mp3-Pfad, Produktionstext)] aus einem Sitzungsordner —
    der Produktionstext kommt aus ``<name>.<weg>.txt``, egal welcher der
    beiden Wege gelaufen ist."""
    out: list[tuple[int, Path, str]] = []
    for mp3 in sorted(ordner.glob("*.mp3")):
        m = re.search(r"(\d+)", mp3.stem)
        if not m:
            continue
        idx = int(m.group(1))
        text = ""
        for weg in WEGE:
            kandidat = mp3.parent / f"{mp3.stem}.{weg}.txt"
            if kandidat.exists():
                text = kandidat.read_text(encoding="utf-8")
                break
        out.append((idx, mp3, text))
    return out


def erzeugen(stuecke: list[tuple[int, Path, str]], video_segmente: list[tuple[float, str]],
            versatz: float, chunk_sekunden: int) -> int:
    """Referenztext je Stück als ``<name>.txt`` schreiben. Gibt die Anzahl zurück."""
    n = 0
    for idx, mp3, _ in stuecke:
        von = idx * chunk_sekunden + versatz
        bis = von + chunk_sekunden
        text = fenster_text(video_segmente, von, bis)
        mp3.with_suffix(".txt").write_text(text, encoding="utf-8")
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ksinr", type=int)
    ap.add_argument("--video", help="YouTube-Video-Id (Vorgabe: eval.transkripte.SITZUNGEN[ksinr])")
    ap.add_argument("--versatz", type=float,
                    help="Zeitversatz Video minus Stream in Sekunden — überspringt die "
                         "automatische Schätzung über TOP-Aufrufe")
    ap.add_argument("--chunk-sekunden", type=int, default=30)
    a = ap.parse_args()

    from council import stt_retain
    from eval import transkripte

    ordner = stt_retain.session_dir(a.ksinr)
    stuecke = gewaehlte_stuecke(ordner)
    if not stuecke:
        print(f"keine aufbewahrten Stücke in {ordner}", file=sys.stderr)
        return 1

    video_id = a.video or transkripte.SITZUNGEN.get(a.ksinr)
    if not video_id:
        print(f"kein Video für Sitzung {a.ksinr} bekannt — mit --video angeben", file=sys.stderr)
        return 1
    video_segmente = transkripte.laden(video_id)

    if a.versatz is not None:
        versatz = a.versatz
    else:
        stream_aufrufe = top_aufrufe([(idx * a.chunk_sekunden, text) for idx, _, text in stuecke])
        versatz = schaetze_versatz(stream_aufrufe, top_aufrufe(video_segmente))
        if versatz is None:
            print("kein gemeinsamer Tagesordnungspunkt-Aufruf gefunden — --versatz von Hand angeben",
                  file=sys.stderr)
            return 1
        print(f"Zeitversatz geschätzt: {versatz:+.1f} s (Video − Stream)")

    n = erzeugen(stuecke, video_segmente, versatz, a.chunk_sekunden)
    print(f"{n} Referenztexte in {ordner} geschrieben")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
