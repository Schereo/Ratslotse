"""Jede Seite des Web-Frontends trägt einen eigenen Titel.

Anlass (Review 10/2026): Zwanzig Seiten — der ganze Haushalt, das Konto, die
Merkliste, das Quiz, die Ideen und alle Anmelde-Seiten — hießen im Tab, in
der Verlaufsliste und für Screenreader gleich: „Ratslotse — Oldenburger
Ratsinformationen verständlich", der Titel des Wurzel-Layouts. Wer fünf Tabs
offen hat, findet so keinen wieder; und Lotti fällt auf den Seitentitel
zurück, wo die Überschrift fehlt (``app/(app)/dashboard/layout.tsx``).

Der Weg ist immer derselbe: ``metadata`` oder ``generateMetadata`` in der
Seite, oder — weil die meisten Seiten Client-Komponenten sind — in einem
kleinen ``layout.tsx`` daneben. Gezählt wird ein Titel aus der Seite selbst
oder aus einem Layout auf dem Weg zu ihr, außer dem Wurzel-Layout und der
App-Hülle.
"""
from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "web" / "frontend" / "app"

#: Diese Layouts geben ihren Titel an ALLE Seiten darunter weiter und zählen
#: deshalb nicht als eigener Titel einer Seite.
ALLGEMEIN = {APP / "layout.tsx", APP / "(app)" / "layout.tsx"}

#: Seiten, die den Titel des Wurzel-Layouts mit Absicht tragen. Mit Grund.
AUSNAHMEN: dict[str, str] = {}

_METADATEN = re.compile(r"export\s+(?:const\s+metadata\b|(?:async\s+)?function\s+generateMetadata\b)")


def _route(page: Path) -> str:
    teile = [t for t in page.parent.relative_to(APP).parts
             if not (t.startswith("(") and t.endswith(")"))]
    return "/" + "/".join(teile)


def _hat_titel(page: Path) -> bool:
    kandidaten = [page]
    d = page.parent
    while d != APP.parent:
        kandidaten.append(d / "layout.tsx")
        d = d.parent
    for datei in kandidaten:
        if datei in ALLGEMEIN or not datei.exists():
            continue
        if _METADATEN.search(datei.read_text(encoding="utf-8")):
            return True
    return False


def _seiten() -> list[Path]:
    return sorted(APP.rglob("page.tsx"))


def test_es_gibt_seiten():
    assert len(_seiten()) > 40


def test_jede_seite_hat_einen_eigenen_titel():
    ohne = [_route(p) for p in _seiten()
            if _route(p) not in AUSNAHMEN and not _hat_titel(p)]
    assert not ohne, (
        "Diese Seiten tragen nur den Titel des Wurzel-Layouts:\n  "
        + "\n  ".join(ohne)
        + "\nIn der Seite `export const metadata = { title: … }` setzen — ist sie "
          "eine Client-Komponente, in einem `layout.tsx` daneben (Vorlage: "
          "app/(app)/account/layout.tsx). Gibt es Lottis Seitenwissen für die "
          "Route (kern/knowledge.py), denselben Titel nehmen.")


def test_keine_ueberfluessige_ausnahme():
    routen = {_route(p): p for p in _seiten()}
    ueberfluessig = [a for a in AUSNAHMEN
                     if a not in routen or _hat_titel(routen[a])]
    assert not ueberfluessig, f"AUSNAHMEN braucht diese Einträge nicht mehr: {ueberfluessig}"
