"""Welche Fachwörter eine Leseseite (Punkt, Beschluss, Sitzung) am Wort erklärt.

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


def decision_texts(detail: dict) -> list[str]:
    """Die Lesetexte einer Beschluss-Seite in der Reihenfolge, in der sie dort
    stehen: Lottis Kurzfassung, der amtliche Wortlaut, „So stand es in der
    Vorlage" (Dossier), zuletzt „Warum es dazu kam" (Auszug der Vorlage)."""
    d = detail.get("decision") or {}
    texte: list[str | None] = [d.get("simple_summary"), d.get("official_text")]
    for abschnitt in (detail.get("template_dossier") or {}).get("sections") or []:
        texte.extend(a.get("text") for a in abschnitt.get("statements") or [])
    # Zeilenweise: Im Auszug ist eine Zeile ein Absatz (gemessen an 148
    # Auszügen: harte Umbrüche mitten im Satz im Median keine). Die Seite klappt
    # die Erklärung unter der Zeile auf, in der das Wort steht — eine
    # Fundstelle darf deshalb nicht über einen Zeilenwechsel reichen.
    texte.extend(((detail.get("template") or {}).get("excerpt") or "").split("\n"))
    return [t.strip() for t in texte if t and t.strip()]


def decision_terms(detail: dict, vorschlaege: list[dict] | None = None) -> list[dict]:
    """Wie :func:`item_terms`, für die Beschluss-Seite."""
    texte = decision_texts(detail)
    begriffe = glossar.fuer_seite(texte, max_n=MAX_BEGRIFFE)
    if vorschlaege:
        begriffe += document_terms(texte, vorschlaege, begriffe)
    return begriffe[:MAX_BEGRIFFE]


#: Die Sitzungsseite ist eine Liste von Karten, kein Lesetext: je Karte
#: höchstens so viele Unterstreichungen …
MAX_JE_KARTE = 2
#: … und auf der ganzen Seite höchstens so viele.
MAX_SITZUNG = 12
_OHNE_BUCHSTABEN_VORN = re.compile(r"^[^\W\d_]+\s+")


def _top_key(nummer: str | None) -> str:
    """„Ö 7.1" → „7.1" — derselbe Schlüssel wie ``topKey`` in der Seite."""
    return _OHNE_BUCHSTABEN_VORN.sub("", nummer or "").strip()


def session_cards(session: dict) -> list[tuple[str, str | None, list[str]]]:
    """Je Karte der Sitzungsseite Punktnummer, Vorlagennummer und die Texte,
    die die Karte zeigt: die Kurzfassung (nach dem Protokoll die des
    Beschlusses) und — nur vor dem Protokoll — „Warum wichtig".

    Nur Punkte mit eigener Karte: Der Kurs kennt sie (Projekt-Überschriften
    und Nichtöffentliches nicht), Formalien und Formalakte stehen gebündelt
    in schlanken Zeilen, Fragestunde und Anfragen tragen feste Sätze der Seite.
    Im Zweifel fehlt hier eine Karte — dann bleibt ein Wort ununterstrichen,
    statt dass eine Fundstelle auf einen Text zeigt, den niemand sieht."""
    beschluss: dict[str, str | None] = {}
    for d in session.get("decisions") or []:
        if d.get("kind") != "decision" or not d.get("item_number"):
            continue
        beschluss.setdefault(_top_key(d["item_number"]), d.get("simple_summary") or d.get("summary") or None)
    kurs = (session.get("course") or {}).get("items") or {}
    vorher = not session.get("has_protocol")
    karten: list[tuple[str, str | None, list[str]]] = []
    for punkt in session.get("agenda_items") or []:
        nr = punkt.get("item_number") or ""
        ci = kurs.get(nr)
        if not ci or ci.get("formality") or ci.get("formal_act") or ci.get("type") in ("question_time", "inquiries"):
            continue
        texte = [beschluss.get(_top_key(nr)) or punkt.get("social_text") or punkt.get("summary"),
                 ci.get("important_reason") if vorher and ci.get("important") else None]
        texte = [t.strip() for t in texte if t and t.strip()]
        if texte:
            karten.append((nr, (punkt.get("template_number") or "").strip() or None, texte))
    return karten


def session_terms(session: dict, vorschlaege: dict[str, list[dict]] | None = None) -> list[dict]:
    """Die Fachwörter der Sitzungsseite: je Begriff die erste Karte, die ihn
    nennt, je Karte höchstens :data:`MAX_JE_KARTE`. ``item`` nennt die Karte —
    gleichlautende Kurzfassungen (sechs Bebauungspläne hintereinander) trügen
    sonst alle dieselbe Unterstreichung. Begriffe aus einer Vorlage
    (``vorschlaege``: Vorlagennummer → geprüfte Begriffe) gelten nur an der
    Karte dieser Vorlage — ihre Erklärung ist für sie geschrieben."""
    aus: list[dict] = []
    namen: set[str] = set()
    for nr, vorlage, texte in session_cards(session):
        karte = [b for b in glossar.fuer_seite(texte, max_n=MAX_SITZUNG) if b["term"].lower() not in namen]
        karte = karte[:MAX_JE_KARTE]
        aus_vorlage = (vorschlaege or {}).get(vorlage) if vorlage else None
        if len(karte) < MAX_JE_KARTE and aus_vorlage:
            neu = [v for v in aus_vorlage if (v.get("term") or "").lower() not in namen]
            karte += document_terms(texte, neu, karte)[:MAX_JE_KARTE - len(karte)]
        for b in karte:
            namen.add(b["term"].lower())
            b["item"] = nr
        aus += karte
        if len(aus) >= MAX_SITZUNG:
            break
    return aus[:MAX_SITZUNG]
