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

import re

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


#: Zusammen höchstens so viele Unterstreichungen je Seite — mehr liest sich
#: wie ein Lückentext.
MAX_BEGRIFFE = 8
_BUCHSTABE = r"[^\W\d_]"


def _stellen(begriffe: list[dict], texte: list[str]) -> dict[int, list[tuple[int, int]]]:
    """Wo auf der Seite schon unterstrichen wird: Text-Nummer → Spannen."""
    belegt: dict[int, list[tuple[int, int]]] = {}
    for b in begriffe:
        for i, text in enumerate(texte):
            pos = text.find(b["snippet"])
            if pos >= 0:
                von = pos + b["offset"]
                belegt.setdefault(i, []).append((von, von + len(b["form"])))
                break
    return belegt


def document_terms(texte: list[str], vorschlaege: list[dict], schon: list[dict]) -> list[dict]:
    """Die geprüften Begriffe aus der Vorlage (``council/vorlage_begriffe.py``)
    in der Form der Seite: erste Fundstelle als wörtliches Stück plus Stelle.
    Ein Begriff, der auf DIESER Seite nicht steht (die Kurzfassung einer
    anderen Sitzung nannte ihn), entfällt still; ebenso einer, der eine schon
    unterstrichene Stelle überlappt."""
    belegt = _stellen(schon, texte)
    namen = {b["term"].lower() for b in schon}
    aus: list[dict] = []
    for v in vorschlaege:
        begriff = v.get("term") or ""
        if not begriff or begriff.lower() in namen:
            continue
        muster = re.compile(rf"(?<!{_BUCHSTABE}){re.escape(begriff)}(?!{_BUCHSTABE})")
        for i, text in enumerate(texte):
            m = muster.search(text)
            if not m:
                continue
            if any(m.start() < bis and m.end() > von for von, bis in belegt.get(i, [])):
                break   # erste Nennung steckt in einem schon erklärten Wort
            von = max(0, m.start() - glossar._UMGEBUNG)  # noqa: SLF001 — dieselbe Umgebung wie beim Glossar
            aus.append({"term": begriff, "form": m.group(0),
                        "snippet": text[von:m.end() + glossar._UMGEBUNG],  # noqa: SLF001
                        "offset": m.start() - von, "explanation": v["explanation"], "kind": "document"})
            belegt.setdefault(i, []).append((m.start(), m.end()))
            namen.add(begriff.lower())
            break
    return aus


def item_terms(punkt: dict, vorschlaege: list[dict] | None = None) -> list[dict]:
    """Geprüftes Glossar zuerst, dann — hinter dem Schalter
    ``begriffe-aus-vorlage`` — die Begriffe aus der Vorlage."""
    texte = item_texts(punkt)
    begriffe = glossar.fuer_seite(texte, max_n=MAX_BEGRIFFE)
    if vorschlaege:
        begriffe += document_terms(texte, vorschlaege, begriffe)
    return begriffe[:MAX_BEGRIFFE]
