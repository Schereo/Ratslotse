"""Backend und Frontend müssen dieselbe Beleg-Regel anwenden.

**Die Regel steht zweimal da**, und das ist unvermeidlich: Der Server
entscheidet, welche Beschluss-ids eine Antwort zitiert (``council/qa.py``), das
Frontend rendert daraus die Fußnoten (``web/frontend/lib/qa-belege.ts``). Ein
regulärer Ausdruck reist nicht über die Schnittstelle.

**Was passiert, wenn sie auseinanderlaufen.** Der Server meldet ``cited: [8525]``
und putzt die Klammer, das Frontend erkennt sie nicht als Marker und zeigt sie
als rohen Text — oder umgekehrt: Das Frontend nummeriert eine Klammer als
Fußnote 3, die der Server gar nicht mitzählt, und die Fußnote zeigt auf den
falschen Beschluss. Beides sieht auf keiner Seite nach einem Fehler aus; die
Suite bleibt grün, weil jede Seite ihre eigene Regel prüft. Genau davor warnt
``tests/CLAUDE.md`` unter „Kein Test gegen die eigene Fixture".

Der Wächter vergleicht deshalb die Muster selbst und rechnet beide
Implementierungen an denselben Beispielen gegeneinander.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from council.qa import _CITE_RE, citation_ids

WURZEL = Path(__file__).resolve().parents[1]
BELEGE_TS = WURZEL / "web" / "frontend" / "lib" / "qa-belege.ts"


def _ts_quelle(name: str) -> str:
    """Den Wert einer ``export const X = String.raw`…``-Zeile lesen."""
    text = BELEGE_TS.read_text(encoding="utf-8")
    m = re.search(rf"export const {name} = String\.raw`([^`]*)`", text)
    assert m, (
        f"{name} steht nicht mehr als String.raw-Konstante in "
        f"{BELEGE_TS.relative_to(WURZEL)} — dieser Wächter kann die Regel dann "
        "nicht mehr lesen. Entweder die Schreibweise wiederherstellen oder den "
        "Test nachziehen.")
    return m.group(1)


def test_die_beschluss_klammer_ist_beidseitig_dieselbe():
    """Bis auf die Fanggruppe muss das Muster Zeichen für Zeichen passen.

    Python fängt den Inhalt (``citation_ids`` bekommt ``m.group(1)``), das
    Frontend arbeitet mit der ganzen Klammer. Das ist der einzige erlaubte
    Unterschied.
    """
    py = _CITE_RE.pattern
    ts = _ts_quelle("CITE_SOURCE")
    assert py.replace("(", "").replace(")", "") == ts, (
        "Die Zitat-Regel ist auseinandergelaufen:\n"
        f"  council/qa.py        {py}\n"
        f"  lib/qa-belege.ts     {ts}\n"
        "Beide Seiten müssen dieselben Klammern erkennen, sonst zeigt eine "
        "Fußnote auf den falschen Beschluss.")


#: Beispiele, an denen sich die Regel entscheidet — echte Modellausgaben.
BEISPIELE = [
    ("[1]", [1]),
    ("[12, 13]", [12, 13]),
    ("[12,13]", [12, 13]),
    # Das Modell hängt trotz Prompt-Regel Datum und Tragweite an. Würde man
    # dort alle Zahlen lesen, entstünde aus „2026-04-20" die Geister-id 2026.
    ("[8525, 2026-04-20, Tragweite: hoch]", [8525]),
    ("[3 Beschluss 22/0348]", [3]),
    ("[siehe oben]", []),
    ("[]", []),
]


@pytest.mark.parametrize("klammer, erwartet", BEISPIELE)
def test_beide_seiten_lesen_dieselben_ids(klammer: str, erwartet: list[int]):
    """Die Python-Seite, an den Beispielen aus dem echten Bestand."""
    inner = klammer[1:-1]
    assert citation_ids(inner) == erwartet


def test_die_beispiele_sind_fuer_das_frontend_dieselben():
    """Und die TypeScript-Seite — nachgerechnet, nicht nachgeschlagen.

    `citationIds` ist vier Zeilen; sie hier nachzubilden wäre ein Test gegen
    eine Kopie. Stattdessen wird die Zusage geprüft, die beide Seiten teilen:
    Was der eine als Marker erkennt, erkennt der andere auch.
    """
    ts = re.compile(_ts_quelle("CITE_SOURCE"))
    for klammer, erwartet in BEISPIELE:
        py_trifft = bool(_CITE_RE.fullmatch(klammer))
        ts_trifft = bool(ts.fullmatch(klammer))
        assert py_trifft == ts_trifft, (
            f"{klammer!r}: Backend {'erkennt' if py_trifft else 'erkennt NICHT'}, "
            f"Frontend {'erkennt' if ts_trifft else 'erkennt NICHT'}. "
            "Die Klammer würde auf einer Seite zur Fußnote und auf der anderen "
            "zu rohem Text.")
        if erwartet:
            assert py_trifft, f"{klammer!r} sollte ein Marker sein"


def test_die_anlagen_klammer_beisst_sich_nicht_mit_der_beschluss_klammer():
    """„[A1]" darf NICHT als Beschluss-Zitat durchgehen.

    Die Beschluss-Klammer muss mit einer Ziffer beginnen — genau deshalb. Fiele
    die Regel, würde aus dem Anlagen-Verweis eine Fußnote auf einen Beschluss,
    den es nicht gibt.
    """
    assert not _CITE_RE.fullmatch("[A1]")
    anl = re.compile(_ts_quelle("ANL_SOURCE"))
    assert anl.fullmatch("[A1]")
    assert not anl.fullmatch("[1]")
