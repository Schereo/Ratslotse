"""Kein Merge-Konflikt bleibt eingecheckt.

Gemessen am 15.09.2026: ``docs-site/src/content/docs/app-und-konten.md`` trug
**zwei** unaufgelöste Konfliktblöcke — eingecheckt mit #1237 (08/2026), über
einen Release nach ``main`` gefahren und seitdem auf ratslotse.de/docs
sichtbar. Niemand hat es gemeldet: Astro rendert ``<<<<<<< HEAD`` klaglos als
Text, die Seite ist lang, und die Stelle steht weit unten.

Der Schaden ist nicht nur Kosmetik. Ein Block hatte die neue
Adresswechsel-Rubrik gegen die Erklärung der beiden Wartezustände gestellt —
zwei Texte, die BEIDE stimmen. Wer so einen Block „auflöst", indem er eine
Hälfte wegwirft, verliert Dokumentation, die niemand vermisst, weil niemand
weiß, dass sie je da war.

Deshalb ein Wächter statt guter Vorsätze (``tests/CLAUDE.md``): Er sieht jede
eingecheckte Datei an, nicht nur die des letzten Diffs, und nennt Datei und
Zeile.

**Warum nicht nur ``<<<<<<<``:** Die schließende Zeile ``>>>>>>>`` allein
bliebe stehen, wenn jemand den Kopf von Hand löscht und den Rest übersieht.
Und ``=======`` fällt bewusst NICHT unter die Prüfung: In Markdown ist es eine
gültige Überschrift (Setext-H1), und ein Wächter, der dauernd grundlos rot
ist, wird abgeschaltet.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]

#: Der Kopf und der Fuß eines Konflikts, jeweils am Zeilenanfang. Git schreibt
#: sieben Zeichen, danach ein Leerzeichen und den Zweignamen (``diff3`` setzt
#: zusätzlich ``|||||||`` für den gemeinsamen Vorfahren dazwischen).
MARKER = re.compile(r"^(?:<{7}|>{7}|\|{7})(?: |$)", re.MULTILINE)

#: Diese Datei erklärt die Marker und muss sie deshalb nennen dürfen.
AUSNAHMEN = {"tests/test_konfliktmarker.py"}


def _dateien() -> list[str]:
    roh = subprocess.run(["git", "ls-files", "-z"], cwd=WURZEL,
                         capture_output=True, text=True, check=True).stdout
    return [p for p in roh.split("\0") if p]


def test_keine_konfliktmarker_im_bestand():
    befunde: list[str] = []
    for rel in _dateien():
        if rel in AUSNAHMEN:
            continue
        datei = WURZEL / rel
        if not datei.is_file() or datei.is_symlink():
            continue
        try:
            text = datei.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # Binärdatei — dort gibt es keine Marker zu finden
        for treffer in MARKER.finditer(text):
            zeile = text.count("\n", 0, treffer.start()) + 1
            befunde.append(f"{rel}:{zeile}")
    assert not befunde, (
        "Unaufgelöste Merge-Konflikte im Bestand:\n  " + "\n  ".join(befunde)
        + "\n\nBeide Seiten lesen, BEVOR eine wegfällt: In app-und-konten.md "
          "stimmten 09/2026 beide, und eine Hälfte wäre still verloren gegangen."
    )


def test_der_waechter_findet_einen_echten_block(tmp_path, monkeypatch):
    """Sonst hielte er nur, solange niemand die Regex kaputtmacht."""
    block = "\n".join(["ok", "<" * 7 + " HEAD", "meins", "=" * 7, "deins",
                       ">" * 7 + " origin/main", "ok"])
    (tmp_path / "a.md").write_text(block, encoding="utf-8")
    zeilen = [f"{t.group(0)!r}" for t in MARKER.finditer(block)]
    assert len(zeilen) == 2, zeilen


def test_eine_markdown_ueberschrift_ist_kein_konflikt():
    """``=======`` unter einer Zeile ist eine Setext-Überschrift, kein Marker —
    genau deshalb prüft der Wächter sie nicht mit."""
    assert not MARKER.search("Titel\n=======\n\nText")
