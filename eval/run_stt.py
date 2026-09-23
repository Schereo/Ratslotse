#!/usr/bin/env python3
"""Transkription des Sitzungs-Mitschnitts — die Suite, der das Audio fehlt.

    python eval/pruefstand.py --suite transkription --modell google/gemini-3-flash-preview --laeufe 2

**Warum sie noch nicht misst.** Bis 09/2026 gab es nirgends aufbewahrtes
Sitzungs-Audio: Der Mitschnitt (``scripts/record_council_livestream.py``)
schrieb seine Stücke in ein ``TemporaryDirectory`` und löschte sie nach dem
Lauf — absichtlich, damit ein abgebrochener Lauf keine alten Stücke in einen
Retry reicht. Seit 23.09.2026 hebt ``council/stt_retain.py`` je Sitzung eine
feste Auswahl auf (``~/.cache/ratslotse/stt/<ksinr>/``, Schalter
``COUNCIL_STT_BEHALTEN``) — die Suite bleibt trotzdem leer, bis die NÄCHSTE
Ratssitzung mit Livestream gelaufen ist (s. ``kern/jobs.py`` bzw. die
Sitzungstabelle für das Datum): Audio zu erfinden oder zu synthetisieren
misst nicht, was im Saal passiert (Hall, Zwischenrufe, Mikrofon aus).

**Was dafür gebraucht wird**, in ``~/.cache/ratslotse/stt/<ksinr>/`` (oder
``RATSLOTSE_STT_AUDIO``, rekursiv durchsucht), je Stück zwei Dateien:

* ``<name>.mp3`` — ein Stück wie im Betrieb (``livestream.start_recording``:
  Mono, 32 kbit/s, 30 s) — liegt nach der nächsten Sitzung automatisch da.
* ``<name>.txt`` — der Referenztext dieses Stücks. Leer heißt: keine Rede
  (Warteschleife, Musik, Pause) — dort ist jede Transkription erfunden. Wird
  aus den YouTube-Untertiteln derselben Sitzung geschnitten:
  ``python eval/stt_referenz.py <ksinr>``.

Daneben liegt, was der PRODUKTIONSWEG für dasselbe Stück tatsächlich
transkribiert hat (``<name>.chunks.txt`` oder ``<name>.gladia.txt``,
s. ``council/stt_retain.py``) — ein Vergleichswert, kein Eingang in diese
Suite.

**Kandidaten müssen Audio annehmen.** GPT-6 Luna kann das nicht, Gemini 3.x
schon; ein Lauf mit einem Modell ohne Audio endet mit einem Anbieterfehler
statt mit einer Zahl.

**Hauptkennzahl, sobald Stücke da sind:** F1 über die Wörter (als Multimenge,
Groß-/Kleinschreibung und Satzzeichen gefaltet) zwischen Transkript und
Referenz, über alle Stücke mit Rede. Eine Wortfolge-Fehlerrate (WER) wäre
genauer, straft aber jede Verschiebung an der Stückgrenze, die bei
geschnittenen Referenzen unvermeidlich ist.
**Harter Befund:** ein Stück ohne Rede, zu dem Text kommt, der die Wächter
des Betriebs (``_looks_fabricated``, ``_looks_looped``) passiert — also Text,
der ungebremst in die Ergebnis-Extraktion liefe.
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))


def ordner() -> Path:
    return Path(os.environ.get("RATSLOTSE_STT_AUDIO")
                or Path.home() / ".cache" / "ratslotse" / "stt")


def stuecke() -> list[tuple[Path, Path]]:
    """Über alle Sitzungs-Unterordner hinweg (``stt_retain.session_dir``
    legt je Sitzung einen eigenen ``<ksinr>/`` an) — ``rglob`` statt
    ``glob``, damit die Suite auch flach abgelegte Stücke (von Hand
    zusammengestellt) findet."""
    d = ordner()
    if not d.is_dir():
        return []
    return [(mp3, mp3.with_suffix(".txt")) for mp3 in sorted(d.rglob("*.mp3"))
            if mp3.with_suffix(".txt").exists()]


def fehlend() -> str | None:
    if stuecke():
        return None
    return (f"kein Sitzungs-Audio: braucht Stücke <name>.mp3 mit Referenz <name>.txt in "
            f"{ordner()}/<ksinr>/ — die Aufbewahrung (council/stt_retain.py) legt sie erst "
            f"nach der nächsten Ratssitzung mit Livestream an, die Referenz kommt danach aus "
            f"`python eval/stt_referenz.py <ksinr>` (s. eval/run_stt.py)")


_MARKE = re.compile(r"\[\s*\d{1,2}:\d{2}\s*\]")


def woerter(text: str) -> Counter:
    text = _MARKE.sub(" ", text or "").lower()
    return Counter(re.findall(r"[a-zäöüß0-9]+", text))


def vergleichen(hyp: str, ref: str) -> dict:
    """Wort-F1 als Multimenge — rein, offline testbar."""
    h, r = woerter(hyp), woerter(ref)
    tp = sum((h & r).values())
    return {"tp": tp, "fp": sum(h.values()) - tp, "fn": sum(r.values()) - tp}


def ein_lauf() -> dict:
    from council import livestream
    zeilen = []
    for mp3, txt in stuecke():
        ref = txt.read_text(encoding="utf-8").strip()
        hyp = livestream.transcribe_chunk(mp3)
        zeile = {"stueck": mp3.name, "rede": bool(ref), "zeichen": len(hyp),
                 **vergleichen(hyp, ref)}
        # Ohne Rede: Was die Wächter durchlassen, ist erfunden.
        zeile["erfunden"] = not ref and len(woerter(hyp)) > 0
        zeilen.append(zeile)
    mit_rede = [z for z in zeilen if z["rede"]]
    tp = sum(z["tp"] for z in mit_rede)
    fp = sum(z["fp"] for z in mit_rede)
    fn = sum(z["fn"] for z in mit_rede)
    return {"n_cases": len(zeilen),
            "f1": round(2 * tp / (2 * tp + fp + fn), 4) if tp else (0.0 if mit_rede else None),
            "erfunden": sum(z["erfunden"] for z in zeilen),
            "leer_trotz_rede": sum(1 for z in mit_rede if not z["zeichen"]),
            "stuecke": zeilen}
