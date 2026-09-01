"""Teilvoten aus dem Original-Abstimmungssatz (raw_result) eines Beschlusses.

Das RIS kennt keine Fraktions- oder Personenvoten — aber die Protokolle
formulieren strittige Abstimmungen oft so: „mehrheitlich bei Gegenstimmen der
Fraktionen SPD und Grüne", „einstimmig bei Enthaltung der CDU-Fraktion".
Dieser Parser holt daraus strukturierte (faction, stance)-Zeilen — die einzige
Quelle, aus der „Wie stimmte Fraktion X?" überhaupt beantwortbar ist.

Bewusst konservativ: Es zählt nur, was das Protokoll ausdrücklich einer
Fraktion/Gruppe zuschreibt (dagegen / enthaltung). Zustimmung wird NIE
abgeleitet — „mehrheitlich angenommen" sagt nicht, wer zustimmte. Gruppen
(„Für Oldenburg", „FDP/Volt") bleiben als Gruppen-Label stehen statt auf
Einzelparteien aufgelöst zu werden — ein Gruppenvotum ist kein belegtes
Parteivotum (siehe council/parties.py, Fraktion ≠ Partei).
"""
from __future__ import annotations

import re

from council import parties

# Marker → (Haltung, Suchrichtung). Substantiv-Formen nennen die Fraktion
# DANACH („bei Gegenstimmen der SPD"), Verb-Formen DAVOR („die SPD stimmte
# dagegen"). Segmente enden am nächsten Marker bzw. an Satzzeichen [.;] —
# Kommas zählen nicht als Grenze, weil Fraktions-AUFZÄHLUNGEN Kommas tragen
# („der Fraktionen SPD, CDU und Grüne").
_MARKERS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"gegen\s+die\s+stimmen?\b|gegenstimmen?\b", re.IGNORECASE), "against", "danach"),
    (re.compile(r"stimm(?:t|te|ten)\s+dagegen", re.IGNORECASE), "against", "davor"),
    (re.compile(r"enthaltung(?:en)?\b", re.IGNORECASE), "abstention", "danach"),
    (re.compile(r"enthielt(?:en)?\s+sich|enthält\s+sich", re.IGNORECASE), "abstention", "davor"),
]

_SENTENCE_BOUND = re.compile(r"[.;]")


def _factions_in_segment(segment: str) -> list[str]:
    """Fraktions-/Gruppen-Labels in einem Satzstück — Gruppen zuerst (und deren
    Mitglieds-Parteien dann nicht doppelt, wenn sie nur im Gruppennamen stecken)."""
    low = segment.lower()
    out: list[str] = []
    for needles, name, _members in parties._GROUPS:
        if all(n in low for n in needles):
            out.append(name)
    for p in parties.parties_in_text(segment):
        if any(p.lower() in g.lower() for g in out):
            continue
        out.append(p)
    return out


def parse_raw_result(raw_result: str | None) -> list[tuple[str, str]]:
    """(faction, stance)-Zeilen aus einem Abstimmungssatz; leer, wenn der Satz
    niemanden ausdrücklich benennt („bei 3 Gegenstimmen" ohne Fraktion)."""
    if not raw_result or not raw_result.strip():
        return []
    text = raw_result.strip()
    marks: list[tuple[int, int, str, str]] = []  # (start, end, stance, richtung)
    for pattern, stance, richtung in _MARKERS:
        for m in pattern.finditer(text):
            marks.append((m.start(), m.end(), stance, richtung))
    if not marks:
        return []
    marks.sort()
    bounds = [m.start() for m in _SENTENCE_BOUND.finditer(text)]
    out: list[tuple[str, str]] = []
    for i, (start, end, stance, richtung) in enumerate(marks):
        if richtung == "danach":
            seg_end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
            seg_end = min([seg_end, *[b for b in bounds if b >= end]] or [seg_end])
            segment = text[end:seg_end]
        else:  # Fraktion steht VOR dem Verb („die SPD stimmte dagegen")
            seg_start = marks[i - 1][1] if i > 0 else 0
            seg_start = max([seg_start, *[b + 1 for b in bounds if b < start]] or [seg_start])
            segment = text[seg_start:start]
        for faction in _factions_in_segment(segment):
            if (faction, stance) not in out:
                out.append((faction, stance))
    return out
