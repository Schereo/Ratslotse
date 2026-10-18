"""Sperrklinke: ``text-muted-foreground/NN`` wird nicht mehr.

DESIGNSPRACHE § 3: „Weniger wichtig heißt nicht schlechter lesbar." Das Token
``--muted-foreground`` hält auf Karte, Seite und Tonfläche in beiden Themes
mindestens 4,5 : 1 — ein ``/60`` dahinter nimmt das wieder weg. Gemessen im
Review 10/2026 (axe): ``/60`` auf Weiß 2,59 : 1, ``/80`` 3,89 : 1, und zwar in
der Seitenleiste, also auf jeder Seite.

Nicht jeder Treffer ist ein Fehler — ein Chevron oder ein Aufzählungspunkt
darf blass sein, er trägt keine Information. Deshalb kein Verbot, sondern
eine Zahl, die **nur sinken darf**: Wer Text gedämpft braucht, nimmt das Token
ohne Bruch; wer ein Zeichen dämpft, nimmt eine Stelle, die schon da ist.
"""
from __future__ import annotations

import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "web" / "frontend"

#: Stand nach dem Review vom 06.10.2026. Sinkt die Zahl, hier nachziehen.
SCHULD = 93

_MUSTER = re.compile(r"text-muted-foreground/\d+")


def _zaehlen() -> int:
    n = 0
    for ordner in ("app", "components"):
        for datei in (FRONTEND / ordner).rglob("*.tsx"):
            n += len(_MUSTER.findall(datei.read_text(encoding="utf-8")))
    return n


def test_gedaempfter_text_wird_nicht_mehr():
    n = _zaehlen()
    assert n <= SCHULD, (
        f"{n} Stellen mit text-muted-foreground/NN, erlaubt sind {SCHULD}. "
        "Text bekommt das Token ohne Bruch (`text-muted-foreground`) — es hält "
        "4,5 : 1, der Bruch nimmt das wieder weg (DESIGNSPRACHE § 3).")


def test_die_zahl_ist_aktuell():
    # Fünf Stellen Luft, damit zwei parallele Aufräum-PRs sich nicht
    # gegenseitig rot machen — mehr nicht, sonst wächst darin Neues unbemerkt.
    n = _zaehlen()
    assert SCHULD - n < 5, (
        f"Es sind nur noch {n} Stellen — SCHULD in {Path(__file__).name} auf {n} "
        "setzen, damit zwischen Zahl und Wirklichkeit kein Puffer wächst.")
