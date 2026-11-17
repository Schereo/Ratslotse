"""Ausnahmen vom axe-Wächter stehen am Element — und ihre Begründung hier.

Der Browsertest ``web/frontend/tests/e2e/35-barrierefreiheit.spec.ts`` verlangt
null Befunde. Was bewusst nicht passt (die Haushalts-Leiste ist so schmal wie
ihr Betrag), trägt ``data-a11y-ausnahme="<regel>"``, und
``a11y-ausnahmen.json`` sagt, warum. Dieser Test hält beide Richtungen:

- Eine Markierung ohne Begründung ist eine stille Abschaltung.
- Eine Begründung ohne Markierung ist eine Ausnahme, die niemand mehr braucht
  und die beim nächsten Mal Neues zudeckt.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / "web" / "frontend"
LISTE = FRONTEND / "tests" / "e2e" / "a11y-ausnahmen.json"
# Fest (`="target-size"`) oder bedingt (`={aus ? "color-contrast" : undefined}`).
_MUSTER = re.compile(r'data-a11y-ausnahme=(?:"([^"]+)"|\{[^}]*?"([a-z-]+)")')


def _begruendet() -> set[str]:
    return {k for k in json.loads(LISTE.read_text(encoding="utf-8")) if not k.startswith("_")}


def _markiert() -> dict[str, list[str]]:
    gefunden: dict[str, list[str]] = {}
    for ordner in ("app", "components"):
        for datei in (FRONTEND / ordner).rglob("*.tsx"):
            for treffer in _MUSTER.finditer(datei.read_text(encoding="utf-8")):
                for regel in (treffer.group(1) or treffer.group(2)).split():
                    gefunden.setdefault(regel, []).append(str(datei.relative_to(FRONTEND)))
    return gefunden


def test_jede_markierung_ist_begruendet():
    fehlt = {r: d for r, d in _markiert().items() if r not in _begruendet()}
    assert not fehlt, (
        f"data-a11y-ausnahme ohne Begründung: {fehlt}. "
        f"Warum die Regel dort nicht gilt, gehört in {LISTE.relative_to(FRONTEND.parent.parent)}.")


def test_jede_begruendung_wird_gebraucht():
    ueber = _begruendet() - set(_markiert())
    assert not ueber, (
        f"Begründet, aber nirgends markiert: {sorted(ueber)}. "
        f"Eintrag aus {LISTE.relative_to(FRONTEND.parent.parent)} entfernen.")
