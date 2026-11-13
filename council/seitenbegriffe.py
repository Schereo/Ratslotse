"""Welche Fachwörter eine Punkt-Seite am Wort erklärt.

Tim, 13.11.2026: „können wir Fachbegriffe erkennen, die man nicht kennen
könnte und dann einfache Erklärungen vorschlagen wie hier zur Grundsteuer C?"
Die geprüften Erklärungen gab es schon (``kern/glossar.py``) — im Haushalt, im
Quiz und in Lottis Antworten sind die Wörter unterstrichen, auf der
Punkt-Seite fehlten sie.

Entschieden wird hier, nicht im Browser: welche Texte die Seite in welcher
Reihenfolge zeigt, welche Wörter zu alltäglich oder mehrdeutig sind
(``glossar.ALLTAG``, ``glossar.MEHRDEUTIG``) und wo die ERSTE Fundstelle je
Begriff liegt. Die Seite bekommt Fundstelle und Erklärung und unterstreicht.
"""
from __future__ import annotations

from kern import glossar


def item_texts(punkt: dict) -> list[str]:
    """Die Lesetexte einer Punkt-Seite in der Reihenfolge, in der sie dort
    stehen: Kurzfassung, „Warum wichtig", „Aus den Unterlagen" (Dossier oder
    die Felder der Vorlage), die Anträge, zuletzt der amtliche Wortlaut."""
    item = punkt.get("item") or {}
    kurs = punkt.get("course_item") or {}
    felder = punkt.get("template_fields") or {}
    texte: list[str | None] = [item.get("social_text") or item.get("summary")]
    if kurs.get("important"):
        texte.append(kurs.get("important_reason"))
    dossier = punkt.get("dossier") or {}
    for abschnitt in dossier.get("sections") or []:
        texte.extend(a.get("text") for a in abschnitt.get("statements") or [])
    if not dossier.get("sections"):
        texte.append(felder.get("proposed_decision"))
    for antrag in punkt.get("amendments") or []:
        texte.extend((antrag.get(k) or {}).get("text") for k in ("meaning", "reason"))
    if dossier.get("sections"):
        texte.append(felder.get("proposed_decision"))
    texte.extend((felder.get(k) or {}).get("text") for k in ("cost", "climate"))
    # Ohne Randleerraum: Die Seite zeigt manche Texte getrimmt, die Fundstelle
    # (``snippet``) muss in beiden Fassungen wörtlich vorkommen.
    return [t.strip() for t in texte if t and t.strip()]


def item_terms(punkt: dict) -> list[dict]:
    return glossar.fuer_seite(item_texts(punkt))
