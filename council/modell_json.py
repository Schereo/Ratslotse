"""Modellantworten im JSON-Modus robust lesen.

**Der Befund (Review 05.10.2026).** ``response_format={"type":
"json_object"}`` verspricht ein Objekt, garantiert es aber nicht: Ein Modell
antwortet gelegentlich mit einem Array (``[...]``), einem nackten String
(``"..."``) oder mit Einträgen, die selbst keine Objekte sind
(``{"ratings": ["a"]}``). Die Parser riefen darauf ``data.get(…)`` bzw.
``r.get(…)`` — außerhalb ihres ``try`` —, das ``AttributeError`` schlug über
``generate_simple_summaries`` bis ``check_protocols`` durch, und mit ihm
fielen alle Schritte danach aus: Tragweite, Wortbeiträge, Vorlagen, Anlagen,
Beratungsfolge, Orte, Akten und die Ergebnis-Meldungen.

Diese Helfer machen aus jeder solchen Antwort „nichts Brauchbares": ein
leeres Objekt, eine Liste nur aus Objekten, einen leeren Text. Was dann fehlt,
holt der nächste Lauf nach — wie bei jeder anderen unbrauchbaren Antwort.
"""
from __future__ import annotations

import json
from typing import Any


def objekt(roh: str | None) -> dict[str, Any]:
    """Der Antworttext als Objekt — ``{}`` bei allem anderen (auch kaputtem JSON)."""
    try:
        data = json.loads(roh or "{}")
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def eintraege(data: dict[str, Any], schluessel: str) -> list[Any]:
    """Die Liste unter ``schluessel`` — nur die Einträge, die selbst Objekte sind.

    Typisiert als ``list[Any]``, nicht ``list[dict]``: Die Aufrufer lesen die
    Felder mit ``int(r.get("id"))`` im ``try`` — ein ``dict[str, Any]`` machte
    daraus ``Any | None`` und für pyright einen Befund je Feld, obwohl der
    ``TypeError`` dort gefangen wird."""
    wert = data.get(schluessel)
    if not isinstance(wert, list):
        return []
    return [e for e in wert if isinstance(e, dict)]


def text(data: dict[str, Any], schluessel: str) -> str:
    """Ein Textfeld — ``""``, wenn es fehlt oder kein String ist."""
    wert = data.get(schluessel)
    return wert.strip() if isinstance(wert, str) else ""
