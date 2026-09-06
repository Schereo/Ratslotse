#!/usr/bin/env python3
"""Der Schuldenstand der Typprüfung — er darf nur sinken.

**Wozu.** `pyrightconfig.json` beschreibt den harten Gate: `kern/` und der
Backend-Kern müssen NULL Befunde haben. Alles andere steht außerhalb, und das
hieße ohne diese Prüfung: gar keine. Ein neues ``x.split()[0]`` auf einem
``str | None`` in ``council/`` fiele niemandem auf.

Die Sperrklinke dreht das um, ohne Aufräumen zu verlangen: Sie zählt die
Befunde je Bereich, und die Zahl darf nicht STEIGEN. Wer eine Datei anfasst
und dabei einen Befund erzeugt, merkt es sofort.

**Warum hier und nicht in der Testsuite.** Der Lauf braucht pyright über den
ganzen Bestand. Als pytest-Test hat er die Testprüfung in der CI von drei auf
**elf Minuten** verlängert — neben dem ohnehin vorhandenen pyright-Schritt
kostet dieselbe Arbeit Sekunden, weil die Node-Laufzeit dort schon warm ist.

**Warum die Zahlen etwas Luft haben.** Gemessen am 04.09.2026 auf zwei
Umgebungen:

===================  ==========  =====
Bereich              Entwickler  CI
===================  ==========  =====
council/                    194    190
scripts/                     44     43
===================  ==========  =====

pyright löst Typen über die INSTALLIERTEN Pakete auf, und die sind nie
bitgleich. Die Schranke ist deshalb der höhere der beiden Werte: Was darunter
liegt, ist in Ordnung. Der Preis ist ein Puffer von wenigen Befunden — der
Alternative, an einem Wert festzuhalten, den eine der beiden Umgebungen nie
erreicht, wäre eine Prüfung, die reihum grundlos rot ist.

Aufruf::

    python scripts/pruefe_typschulden.py           # prüft
    python scripts/pruefe_typschulden.py --zeigen  # nur die Zahlen nennen
"""
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
RATSCHE = WURZEL / "pyrightconfig.ratsche.json"

#: Obergrenze je Bereich — die Zahl DARF NUR SINKEN. Wer aufräumt, trägt die
#: neue ein; das ist der halbe Lohn der Arbeit. Fällt ein Bereich auf null,
#: gehört er in `include` von `pyrightconfig.json`, nicht mehr hierher.
SCHULDEN = {
    "council": 194,
    "web/backend/app/routers": 111,
    "scripts": 44,
    "eval": 7,
}


def _bereich(rel: str) -> str:
    if rel.startswith("web/backend/app/routers/"):
        return "web/backend/app/routers"
    if rel.startswith("web/backend/app/"):
        return "web/backend/app"
    return rel.split("/")[0]


def zaehlen(python: str) -> dict[str, int]:
    r = subprocess.run(
        [python, "-m", "pyright", "--pythonpath", python,
         "--project", str(RATSCHE), "--outputjson"],
        cwd=WURZEL, capture_output=True, text=True)
    if not r.stdout.strip():
        raise SystemExit(f"pyright lieferte nichts:\n{r.stderr[:400]}")
    daten = json.loads(r.stdout)
    aus: collections.Counter[str] = collections.Counter()
    for d in daten["generalDiagnostics"]:
        if d["severity"] != "error":
            continue
        rel = Path(d["file"]).resolve().relative_to(WURZEL).as_posix()
        aus[_bereich(rel)] += 1
    return dict(aus)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--zeigen", action="store_true", help="nur die Zahlen nennen")
    args = p.parse_args()

    ist = zaehlen(sys.executable)

    if args.zeigen:
        for bereich in sorted(set(SCHULDEN) | set(ist)):
            print(f"  {bereich:26} {ist.get(bereich, 0):4}  (Schranke {SCHULDEN.get(bereich, 0)})")
        return 0

    # Der harte Gate muss null bleiben — er hat seine eigene Prüfung, aber
    # hier fiele ein Bruch ebenfalls auf, und zwar mit Zahl.
    gate = {b: n for b, n in ist.items() if b not in SCHULDEN and n}
    if gate:
        print("FEHLER: Befunde im harten Geltungsbereich:", file=sys.stderr)
        for b, n in sorted(gate.items()):
            print(f"  {b}: {n}", file=sys.stderr)
        return 1

    gestiegen = {b: (ist.get(b, 0), s) for b, s in SCHULDEN.items() if ist.get(b, 0) > s}
    if gestiegen:
        print("FEHLER: Neue Typbefunde außerhalb des Geltungsbereichs:", file=sys.stderr)
        for b, (jetzt, schranke) in sorted(gestiegen.items()):
            print(f"  {b}: {jetzt} statt höchstens {schranke} (+{jetzt - schranke})",
                  file=sys.stderr)
        print("\nZeig sie dir an:", file=sys.stderr)
        print("  .venv/bin/pyright --project pyrightconfig.ratsche.json <bereich>",
              file=sys.stderr)
        return 1

    # Deutlich unter der Schranke? Dann ist aufgeräumt worden, und die Zahl
    # gehört nachgetragen — sonst wächst ein Puffer, in dem neue Befunde
    # unbemerkt Platz haben. „Deutlich", weil die Umgebungen um ein paar
    # Befunde auseinanderliegen (s. Modul-Docstring).
    LUFT = 10
    gesunken = {b: (ist.get(b, 0), s) for b, s in SCHULDEN.items()
                if s - ist.get(b, 0) > LUFT}
    if gesunken:
        print("Aufgeräumt — schön! Trag die neuen Zahlen in SCHULDEN ein", file=sys.stderr)
        print("(scripts/pruefe_typschulden.py):", file=sys.stderr)
        for b, (jetzt, schranke) in sorted(gesunken.items()):
            print(f'  "{b}": {jetzt},   # war {schranke}', file=sys.stderr)
        return 1

    gesamt = sum(ist.get(b, 0) for b in SCHULDEN)
    print(f"Schuldenstand in Ordnung: {gesamt} Befunde außerhalb des "
          f"Geltungsbereichs, keiner darin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
