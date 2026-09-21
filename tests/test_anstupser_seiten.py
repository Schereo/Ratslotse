"""Die Liste im Frontend und die Wahrheit im Backend dürfen nicht auseinander.

Lottis Anstupser entscheidet, BEVOR irgendein Endpunkt gerufen wird — er
wartet ja gerade darauf, dass jemand liest, ohne zu fragen. Deshalb steht die
Liste der erlaubten Seiten zweimal da: als ``PageKnowledge.nudge`` in
``kern/knowledge.py`` und als Aufzählung in
``web/frontend/lib/anstupser-seiten.ts``.

Seit die App mitklopft, sind es **drei** Kopien: dazu
``ExplainScreen.nudgeRoutes`` in ``ios/Packages/RatslotseAPI``. Dieselbe
Begründung, dasselbe Risiko.

Drei Wahrheiten laufen auseinander, und zwar lautlos: Eine Seite, die im
Backend freigegeben ist und in einem Client fehlt, klopft dort nie an — das
sieht aus wie „der Anstupser wird kaum angenommen" und ist ein Tippfehler.
"""
from __future__ import annotations

import re
from pathlib import Path

from kern import knowledge

WURZEL = Path(__file__).resolve().parents[1]
LISTE = WURZEL / "web" / "frontend" / "lib" / "anstupser-seiten.ts"
SWIFT = (WURZEL / "ios" / "Packages" / "RatslotseAPI" / "Sources" / "RatslotseAPI"
         / "Assistant.swift")


def _frontend() -> set[str]:
    text = LISTE.read_text(encoding="utf-8")
    block = text[text.index("ANSTUPSER_SEITEN"):text.index("] as const")]
    return set(re.findall(r'"([^"]+)"', block))


def _app() -> set[str]:
    text = SWIFT.read_text(encoding="utf-8")
    block = text[text.index("nudgeRoutes: Set<String> = ["):]
    block = block[:block.index("]")]
    return set(re.findall(r'"([^"]+)"', block))


def _backend() -> set[str]:
    return {route for route, k in knowledge.PAGES.items() if k.nudge}


def test_beide_listen_sind_gleich():
    fehlt_vorn = _backend() - _frontend()
    zu_viel = _frontend() - _backend()
    assert not fehlt_vorn and not zu_viel, (
        "Die Anstupser-Seiten laufen auseinander.\n"
        f"  Im Backend freigegeben, im Frontend nicht: {sorted(fehlt_vorn)}\n"
        f"  Im Frontend, aber im Backend nicht: {sorted(zu_viel)}\n"
        "Die Wahrheit ist kern/knowledge.py (`nudge=True`); zieh "
        "web/frontend/lib/anstupser-seiten.ts nach.")


def test_die_app_kennt_dieselben_seiten():
    fehlt = _backend() - _app()
    zu_viel = _app() - _backend()
    assert not fehlt and not zu_viel, (
        "Die Anstupser-Seiten der App laufen auseinander.\n"
        f"  Im Backend freigegeben, in der App nicht: {sorted(fehlt)}\n"
        f"  In der App, aber im Backend nicht: {sorted(zu_viel)}\n"
        "Die Wahrheit ist kern/knowledge.py (`nudge=True`); zieh "
        "ios/Packages/RatslotseAPI/Sources/RatslotseAPI/Assistant.swift nach.")


def test_keine_gesperrte_seite_klopft_an():
    """Wo es Lotti gar nicht gibt, kann sie auch nicht anklopfen."""
    assert not _frontend() & set(knowledge.OHNE_ERKLAERUNG)


def test_auf_fragen_wird_nie_angeklopft():
    """Dort fragt man schon — eine Blase daneben wäre eine zweite
    Aufforderung zu derselben Sache."""
    assert "/fragen" not in _frontend()
    assert knowledge.PAGES["/fragen"].nudge is False


def test_die_liste_ist_nicht_leer():
    """Eine leere Liste bestünde jeden Vergleich und klopfte nirgends an."""
    assert len(_frontend()) >= 10
