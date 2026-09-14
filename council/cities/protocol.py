"""Eine Niederschrift in ihre Tagesordnungspunkte zerlegen.

Die Sitzungs-PDF ist das Einzige, worin steht, **warum** ein Rat so
entschieden hat. Sie umfasst vier bis vierzig Seiten und behandelt zwanzig
Themen; die Begründung zu *einem* Beschluss steht in *einem* Abschnitt. Ein
Sprachmodell die ganze Sitzung lesen zu lassen, um einen Punkt zu finden, ist
teuer und rät. Schneiden ist Regelarbeit — und Regelarbeit ist messbar.

**Geschnitten wird entlang der Tagesordnung, die wir schon haben.** Der erste
Entwurf suchte nur nach Überschriften und scheiterte gemessen: In Braunschweig
und Potsdam beginnt jeder zweite Beschlusstext mit „1. Die Verwaltung setzt
…", und eine Regel auf nackte Nummern hält das für einen neuen
Tagesordnungspunkt (gemessen 10.09.2026: 5 statt 7 Abschnitte, und die
gefundenen trugen Beschlusssätze als Titel). Die Schnittstelle liefert aber zu
jeder Sitzung ihre Punkte mit Nummer und Titel — damit wird aus dem Raten ein
Nachschlagen: Für jeden bekannten Punkt wird **seine** Überschrift im Text
gesucht, und der Abschnitt reicht bis zur nächsten.

**Die Schreibweise folgt dem Layout, nicht dem Hersteller.** Osnabrück und
Braunschweig sprechen beide ALLRIS 4, schreiben ihre Protokolle aber
verschieden (``Zu 4  Titel`` gegen ``4. Titel``). Das Layout steht im Text und
wird dort erkannt.

**Jede Niederschrift enthält ihre Tagesordnung ZWEIMAL** — erst als
Inhaltsverzeichnis, dann als Protokolltext. Deshalb gewinnt bei mehreren
Fundstellen derselben Nummer die **hintere** mit passendem Titel: Das
Verzeichnis steht immer vorn.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from council.cities.adapters._common import normalize_title
from council.cities.store import CitiesStore

#: Fassung der Schneideregeln. Ändert sich eine Regel, steigt sie — dann
#: liegen alte und neue Abschnitte nebeneinander und lassen sich vergleichen,
#: statt dass jemand aufräumen muss (dieselbe Regel wie bei den Annotatoren).
SPLITTER_VERSION = "1"

#: Kürzer als das ist kein Abschnitt, sondern eine Zeile aus dem
#: Inhaltsverzeichnis, die dem Titelabgleich entgangen ist.
MIN_TEXT = 40

#: So viel Text hinter der Überschrift wird für den Titelabgleich angesehen.
TITEL_FENSTER = 160

LAYOUTS = ("punkt", "zu", "nummer")

#: **Der Zeilenanfang darf eingerückt sein.** Osnabrück schreibt seine
#: Protokolle seit 2024 mit einem führenden Leerzeichen vor der Nummer
#: (`` 3.1. Bessere und feste Oberflächen …``); eine Regel, die auf `^\d`
#: besteht, findet dort gar nichts — gemessen 0 von 194 Punkten, während
#: dieselbe Stadt 2026 zu 92 % traf. Zwei Schreibweisen derselben Stadt, und
#: die Regel muss beide können.
_EIN = r"^[ \t]{0,4}"

_PUNKT_RE = re.compile(_EIN + r"Punkt\s+(\d+(?:\.\d+)*)\s+der\s+Tagesordnung\s*$",
                       re.MULTILINE)
_ZU_RE = re.compile(_EIN + r"Zu\s+(\d+(?:\.\d+)*)\s{1,4}(?=\S)", re.MULTILINE)
#: Eine Nummer am Zeilenanfang, dahinter ein Titel, der mit einem Großbuchstaben
#: beginnt. Ohne die Großschreibung trifft die Regel jede Zahl in einem
#: Fließtext-Umbruch („… 2019 wurde beschlossen").
_NUMMER_RE = re.compile(_EIN + r"(\d+(?:\.\d+)*)\.?\s{1,3}(?=[A-ZÄÖÜ])", re.MULTILINE)

_REGELN = {"punkt": _PUNKT_RE, "zu": _ZU_RE, "nummer": _NUMMER_RE}


@dataclass(frozen=True)
class Section:
    """Ein Tagesordnungspunkt, wie er in der Niederschrift steht."""

    #: Kennung des Tagesordnungspunkts — der Abschnitt ist einem zugeordnet.
    key: str
    number: str
    title: str
    text: str
    start: int
    end: int


def detect_layout(text: str) -> str | None:
    """Welche Schreibweise benutzt diese Niederschrift?

    Die Reihenfolge ist von speziell nach allgemein: ``Punkt 4 der
    Tagesordnung`` und ``Zu 4 …`` sind eindeutig, eine nackte Nummer ist es
    nicht — sie steht auch in jedem Inhaltsverzeichnis und in jeder
    Beschlussaufzählung.
    """
    for layout in ("punkt", "zu"):
        if len(_REGELN[layout].findall(text)) >= 2:
            return layout
    return "nummer" if len(_NUMMER_RE.findall(text)) >= 4 else None


def split_protocol(text: str, items: Sequence[tuple[str, str, str]],
                   layout: str | None = None) -> list[Section]:
    """Die Niederschrift entlang ihrer Tagesordnung zerlegen.

    ``items`` sind die Punkte der Sitzung als ``(kennung, nummer, titel)`` —
    genau das, was ``agenda_items`` je Sitzung führt. Zurück kommen die
    Abschnitte in Dokumentreihenfolge, jeder einem Punkt zugeordnet. Punkte,
    deren Überschrift nicht zu finden ist, fehlen; das ist kein Fehler,
    sondern die ehrliche Antwort (nicht öffentliche Punkte etwa stehen im
    öffentlichen Protokoll gar nicht).
    """
    if not text or not items:
        return []
    layout = layout or detect_layout(text)
    if layout not in _REGELN:
        return []
    treffer = list(_REGELN[layout].finditer(text))
    if not treffer:
        return []

    je_nummer: dict[str, list[re.Match]] = {}
    for m in treffer:
        je_nummer.setdefault(_nummer(m.group(1)), []).append(m)

    # Erst jedem Punkt seine Fundstelle geben, dann in Dokumentreihenfolge
    # schneiden — die Reihenfolge der Tagesordnung muss nicht die des
    # Dokuments sein (Potsdam führt „10" zwischen „1" und „2").
    anker: dict[int, tuple[str, str, str]] = {}
    for key, nummer, titel in items:
        beste = _beste_fundstelle(je_nummer.get(_nummer(nummer)) or [], text, titel)
        if beste is None:
            continue
        # Zwei Punkte auf derselben Fundstelle: Der erste gewinnt. Das ist
        # kein Sonderfall, sondern der Regelfall bei den doppelt abgelegten
        # Punkten mancher Städte (zwei Kennungen, dieselbe Sache).
        anker.setdefault(beste.start(), (key, nummer.strip(), titel))

    grenzen = sorted(anker)
    # Ein Abschnitt endet an der nächsten ERKANNTEN Überschrift, nicht am
    # nächsten Anker: Sonst schluckt ein Punkt ohne Fundstelle den Text des
    # vorherigen mit.
    starts = sorted({m.start() for m in treffer})

    abschnitte: list[Section] = []
    for pos in grenzen:
        key, nummer, titel = anker[pos]
        m = next(m for m in treffer if m.start() == pos)
        ende = next((s for s in starts if s > pos), len(text))
        rumpf = text[m.end():ende].strip()
        if len(rumpf) < MIN_TEXT:
            continue
        abschnitte.append(Section(key, nummer, titel, rumpf, pos, ende))
    return abschnitte


def _beste_fundstelle(kandidaten: list[re.Match], text: str,
                      titel: str) -> re.Match | None:
    """Welche Fundstelle dieser Nummer trägt den Titel des Punktes?

    Bei Gleichstand gewinnt die **hintere**: Das Inhaltsverzeichnis steht
    immer vor dem Protokolltext.
    """
    if not kandidaten:
        return None
    worte = [w for w in normalize_title(titel).split() if len(w) > 3][:8]
    beste, bester_wert = None, -1.0
    for m in kandidaten:
        folgt = normalize_title(text[m.end():m.end() + TITEL_FENSTER])
        wert = (sum(1 for w in worte if w in folgt) / len(worte)) if worte else 0.0
        if wert >= bester_wert:
            beste, bester_wert = m, wert
    # Ohne jede Titelübereinstimmung ist die Nummer allein zu wenig — dann
    # steht dort eine Beschlussaufzählung, kein Tagesordnungspunkt.
    return beste if bester_wert >= 0.5 else None


# ------------------------------------------------------------------ Ablage

def attach_sections(main: CitiesStore, meeting_id: str, file_id: str,
                    sections: Sequence[Section]) -> int:
    """Die Abschnitte einer Sitzung ablegen."""
    zeilen = [(file_id, meeting_id, i, s.key, s.number, s.title, s.text)
              for i, s in enumerate(sections)]
    main.put_protocol_sections(SPLITTER_VERSION, zeilen)
    return len(zeilen)


def split_meeting(main: CitiesStore, meeting_id: str, file_id: str,
                  text: str) -> int:
    """Eine Niederschrift schneiden und ablegen — der Weg, den der Cron geht."""
    punkte = [(p["id"], p["number"] or "", p["name"] or "")
              for p in main.agenda_items(meeting_id)]
    return attach_sections(main, meeting_id, file_id,
                           split_protocol(text, punkte))


def _nummer(text: str | None) -> str:
    """``4.``, ``TOP 4`` und ``4`` sind dieselbe Nummer."""
    if not text:
        return ""
    treffer = re.search(r"\d+(?:\.\d+)*", text)
    return treffer.group(0).rstrip(".") if treffer else ""
