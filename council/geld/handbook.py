"""Das Handbuch Beteiligungen — die Regeln zu den städtischen Gesellschaften.

Die Facette ``companies`` sagt, was eine Gesellschaft ist und was sie
erwirtschaftet. Wie die Stadt sie STEUERT — wer bestimmt, wer kontrolliert,
was öffentlich ist, wer prüft —, steht im Handbuch Beteiligungen
(:mod:`council.shareholding_handbook`). Bis 11/2026 kannte Ratslotse es
nicht, und „Darf der Rat dem Aufsichtsrat etwas vorschreiben?" bekam statt
einer Regel einen Steckbrief.

Eine eigene Facette statt eines Zusatzes zu ``companies``, weil die Regeln
auch OHNE Gesellschaftsnamen gefragt werden („Was macht ein Aufsichtsrat?")
und weil eine Facette auf einen Schlag überall ankommt, wo Haushaltswissen
gebraucht wird: KI-Frage, Lotti, Lottis Werkzeuge, MCP und die ausführliche
Recherche (alle über ``qa.geld_kontext``).

Kein Datenbankzugriff: Die Regeln stehen als Code im Repo. Die Store-Methode
ist trotzdem eine — das verlangt das Facetten-Gerüst —, und sie bekommt die
Wörter der ROHEN Frage (``qa.geld_kontext``), nicht die der Expansion.
"""
from __future__ import annotations

from council import geld
from council.store_basis import StoreBasis

NAME = "handbook"


def recognize(text: str, typ: str, facets: set[str]) -> bool:
    from council import shareholding_handbook

    return bool(shareholding_handbook.find(text))


def block(data: dict | None) -> str:
    from council import shareholding_handbook

    return shareholding_handbook.block(data)


class Store(StoreBasis):
    """Store-Mixin: die Handbuch-Regeln zur Frage (ohne Datenbank)."""

    def handbook_context(self, terms: list[str], year: int | None = None) -> dict | None:
        from council import shareholding_handbook

        return shareholding_handbook.context(" ".join(terms))


FACETTE = geld.Facette(
    name=NAME, methode="handbook_context", erkennen=recognize, block=block,
    # Zwei Regeln (MAX_RULES) samt Kopf: über alle Paare gemessen höchstens
    # 2.379 Zeichen (Berichte + Aufsichtsrat), s. tests/test_shareholding_handbook.py.
    mixin=Store, rang=45, grenze=2450,
    probefrage="Was macht ein Aufsichtsrat bei einer städtischen Gesellschaft?")
