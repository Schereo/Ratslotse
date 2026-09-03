"""Wächter: Lottis Tour-Einladung darf nicht an einem Ereignis allein hängen.

Am 03.09.2026 war die Einladung auf Prod ausgefallen, obwohl der Code
ausgeliefert war. Ursache: Sie hörte nur auf ein Ereignis, das der Assistent
beim Abschluss feuert — und wer es in dem Moment nicht hört, hört es nie
wieder. Nicht gehört hat es, wer den Assistenten in einem Tab beendet, der seit
vor einem Deploy offen ist (dort gibt es die Komponente im geladenen Bündel gar
nicht), und ebenso jeder Moment, in dem die App-Hülle nicht steht: das Skelett,
solange ``/auth/me`` läuft, und der Sperrbildschirm vor der Bestätigung.

Der Riegel dagegen ist eine Marke im Speicher, die der **Assistent selbst**
beim Abschluss setzt und die Einladung beim Aufbauen liest. Diese Datei hält
genau das fest — den Schlüssel an einer Stelle, das Setzen im Abschluss, das
Lesen beim Aufbauen.

Warum als Python-Test über den Quelltext: Das Repo hat keinen JS-Testlauf
(s. ``tests/CLAUDE.md``), die Regel ist aber baulich und in einem Diff leicht
zu übersehen — genau der Fall für einen Wächter.
"""
from __future__ import annotations

from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "web" / "frontend"
MARKE = FRONTEND / "lib" / "tour-einladung.ts"
ASSISTENT = FRONTEND / "components" / "onboarding-flow.tsx"
EINLADUNG = FRONTEND / "components" / "tour-einladung.tsx"
HUELLE = FRONTEND / "app" / "(app)" / "layout.tsx"

HINWEIS = (
    "Siehe tests/test_tour_einladung.py — die Einladung muss aus einer "
    "gemerkten Marke leben, nicht aus einem Ereignis allein."
)


@pytest.fixture(scope="module")
def quellen() -> dict[str, str]:
    fehlend = [p.name for p in (MARKE, ASSISTENT, EINLADUNG, HUELLE) if not p.exists()]
    if fehlend:
        pytest.fail(f"Datei(en) fehlen: {', '.join(fehlend)}. {HINWEIS}")
    return {p.name: p.read_text(encoding="utf-8") for p in (MARKE, ASSISTENT, EINLADUNG, HUELLE)}


def test_schluessel_steht_an_genau_einer_stelle(quellen: dict[str, str]) -> None:
    """Der Speicher-Schlüssel gehört in lib/tour-einladung.ts — sonst laufen die
    beiden Seiten beim nächsten Umbenennen auseinander, ohne dass es auffällt."""
    schluessel = '"ratslotse:tour-einladung"'
    assert schluessel in quellen["tour-einladung.ts"], HINWEIS
    for name in ("onboarding-flow.tsx", "tour-einladung.tsx"):
        assert schluessel not in quellen[name], (
            f"{name} schreibt den Schlüssel selbst hin. Nimm einladungStand()/"
            f"merkeEinladung() aus lib/tour-einladung.ts. {HINWEIS}"
        )


def test_assistent_setzt_die_marke_beim_abschluss(quellen: dict[str, str]) -> None:
    """Der Abschluss selbst muss die Marke setzen. Täte das nur der Empfänger
    des Ereignisses, wäre genau der Prod-Ausfall vom 03.09.2026 wieder da."""
    quelle = quellen["onboarding-flow.tsx"]
    assert 'merkeEinladung("offen")' in quelle, (
        'In go("done") fehlt merkeEinladung("offen"). ' + HINWEIS
    )
    # Und zwar im Abschluss-Zweig, nicht irgendwo: Der Zweig beginnt bei
    # `if (next === "done")` und endet an seinem `return;`.
    beginn = quelle.index('if (next === "done")')
    ende = quelle.index("return;", beginn)
    assert 'merkeEinladung("offen")' in quelle[beginn:ende], (
        'merkeEinladung("offen") steht außerhalb des Abschluss-Zweigs. ' + HINWEIS
    )


def test_einladung_liest_die_marke_beim_aufbauen(quellen: dict[str, str]) -> None:
    """Ohne das Lesen beim Aufbauen nützt die Marke nichts: Genau die Fälle, um
    die es geht, sind die, in denen die Komponente erst SPÄTER entsteht."""
    quelle = quellen["tour-einladung.tsx"]
    assert 'einladungStand() === "offen"' in quelle, HINWEIS
    assert 'merkeEinladung("erledigt")' in quelle, (
        "Die Einladung räumt ihre Marke nach dem Beantworten nicht ab — sie käme "
        "bei jedem Aufbauen wieder. " + HINWEIS
    )


def test_huelle_haengt_die_einladung_ein(quellen: dict[str, str]) -> None:
    """Sie hängt bewusst in der App-Hülle und nicht global: Über der Startseite
    oder dem Impressum hätte Lotti nichts zu suchen."""
    assert "<TourEinladung />" in quellen["layout.tsx"], HINWEIS
