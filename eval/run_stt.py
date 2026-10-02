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

**Ersatz-Referenz: der Gladia-Text.** Solange keine YouTube-Fassung der
Sitzung vorliegt (oder der Server sie nicht holen kann), nimmt
``RATSLOTSE_STT_REFERENZ=gladia`` stattdessen ``<name>.gladia.txt`` als
Referenz — was der Streaming-Weg im Betrieb für dasselbe Fenster geliefert
hat. Unabhängig von Gemini ist er, fehlerfrei nicht: Eine F1 dagegen misst
ÜBEREINSTIMMUNG mit Gladia, keine absolute Güte. Für den VERGLEICH zweier
Modelle an denselben Stücken reicht das; die Ergebnisse tragen die Quelle
(``referenz``). Angelegt am 02.10.2026 für den Abschied von Gemini 2.5 Flash
(``.github/workflows/ops-stt-vergleich.yml``).

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


#: Welche Datei als Referenz gilt: leer = ``<name>.txt`` (YouTube, s.
#: ``eval/stt_referenz.py``), ``gladia``/``chunks`` = der Vergleichstext des
#: Produktionswegs (``<name>.<weg>.txt``, s. Docstring).
REFERENZ_ENV = "RATSLOTSE_STT_REFERENZ"


def referenz_quelle() -> str:
    return (os.environ.get(REFERENZ_ENV) or "").strip()


def referenz_pfad(mp3: Path) -> Path:
    quelle = referenz_quelle()
    if quelle:
        return mp3.with_name(f"{mp3.stem}.{quelle}.txt")
    return mp3.with_suffix(".txt")


def stuecke() -> list[tuple[Path, Path]]:
    """Über alle Sitzungs-Unterordner hinweg (``stt_retain.session_dir``
    legt je Sitzung einen eigenen ``<ksinr>/`` an) — ``rglob`` statt
    ``glob``, damit die Suite auch flach abgelegte Stücke (von Hand
    zusammengestellt) findet."""
    d = ordner()
    if not d.is_dir():
        return []
    return [(mp3, referenz_pfad(mp3)) for mp3 in sorted(d.rglob("*.mp3"))
            if referenz_pfad(mp3).exists()]


def fehlend() -> str | None:
    if stuecke():
        return None
    if referenz_quelle():
        return (f"keine Stücke mit <name>.{referenz_quelle()}.txt in {ordner()}/<ksinr>/ "
                f"({REFERENZ_ENV}={referenz_quelle()})")
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
        # Sitzungsordner mit im Namen: Zwei Sitzungen haben beide ein chunk_000.
        zeile = {"stueck": f"{mp3.parent.name}/{mp3.name}", "rede": bool(ref),
                 "zeichen": len(hyp), **vergleichen(hyp, ref),
                 # Der Text selbst — zum Nachlesen von Auslassungen und
                 # Sprecherwechseln, die eine Wort-F1 nicht sieht. Öffentliche
                 # Sitzung, nichts Persönliches über die Rede hinaus.
                 "text": hyp}
        # Ohne Rede: Was die Wächter durchlassen, ist erfunden.
        zeile["erfunden"] = not ref and len(woerter(hyp)) > 0
        zeilen.append(zeile)
    mit_rede = [z for z in zeilen if z["rede"]]
    tp = sum(z["tp"] for z in mit_rede)
    fp = sum(z["fp"] for z in mit_rede)
    fn = sum(z["fn"] for z in mit_rede)
    return {"n_cases": len(zeilen), "referenz": referenz_quelle() or "youtube",
            "f1": round(2 * tp / (2 * tp + fp + fn), 4) if tp else (0.0 if mit_rede else None),
            "erfunden": sum(z["erfunden"] for z in zeilen),
            "leer_trotz_rede": sum(1 for z in mit_rede if not z["zeichen"]),
            "stuecke": zeilen}


def zeigen(pfade: list[Path], breite: int = 240) -> str:
    """Die Stücke mehrerer Ergebnisdateien (``eval/results/pruefstand/
    transkription/*.json``) nebeneinander: je Stück Referenz und jedes
    Modell, mit Wort-F1 — zum Lesen, nicht zum Rechnen."""
    import json
    laeufe = [json.loads(p.read_text(encoding="utf-8")) for p in pfade]
    zeilen: list[str] = []
    for erg in laeufe:
        roh = erg.get("roh") or {}
        zeilen.append(f"{erg.get('modell')} Lauf {erg.get('lauf')}: F1 {roh.get('f1')} · "
                      f"erfunden {roh.get('erfunden')} · leer trotz Rede "
                      f"{roh.get('leer_trotz_rede')} · p50 {erg.get('p50_ms')} ms · "
                      f"p95 {erg.get('p95_ms')} ms · {erg.get('kosten_usd')} $ · "
                      f"Referenz {roh.get('referenz')}")
    namen = [z["stueck"] for z in (laeufe[0].get("roh") or {}).get("stuecke", [])] if laeufe else []
    for name in namen:
        zeilen.append(f"\n--- {name}")
        mp3 = next((m for m, _ in stuecke() if f"{m.parent.name}/{m.name}" == name), None)
        if mp3 is not None:
            ref = referenz_pfad(mp3).read_text(encoding="utf-8").strip()
            zeilen.append(f"  REFERENZ: {ref[:breite]}")
        for erg in laeufe:
            z = next((z for z in (erg.get("roh") or {}).get("stuecke", []) if z["stueck"] == name),
                     None)
            if z is None:
                continue
            f1 = 2 * z["tp"] / (2 * z["tp"] + z["fp"] + z["fn"]) if z["tp"] else 0.0
            text = " ".join((z.get("text") or "").split())
            zeilen.append(f"  {erg.get('modell')} #{erg.get('lauf')} (F1 {f1:.2f}): {text[:breite]}")
    return "\n".join(zeilen)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Ergebnisse der Suite `transkription` nebeneinander")
    ap.add_argument("zeigen", choices=["zeigen"])
    ap.add_argument("dateien", nargs="+", type=Path)
    ap.add_argument("--breite", type=int, default=240)
    a = ap.parse_args()
    print(zeigen(a.dateien, a.breite))
