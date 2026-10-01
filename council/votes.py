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


# ---- Abstimmungsverhältnis (vote) -----------------------------------------

VOTES = ("unanimous", "majority")

# „- einstimmig bei neun Enthaltungen -": Enthaltungen sind keine
# Gegenstimmen, der Beschluss ist einstimmig. Bewusst eng — nur der Satz, der
# außer „einstimmig" und Enthaltungen NICHTS sagt. „einstimmig bei einer
# Gegenstimme" (8590) steht wirklich so im Protokoll und bleibt, wie es ist.
_EINSTIMMIG_MIT_ENTHALTUNGEN = re.compile(
    r"^[\s\-–—.]*einstimmig(?:\s+(?:beschlossen|angenommen))?"
    r"(?:\s*,?\s*(?:bei|mit)\s+(?:\w+\s+)?enthaltung(?:en)?)?[\s\-–—.]*$",
    re.IGNORECASE,
)


#: Die amtliche Formel „gilt als behandelt": Der Ausschuss schließt den
#: Tagesordnungspunkt ab, ohne über den Inhalt zu beschließen (auf Antrag zur
#: Geschäftsordnung; entschieden wird ggf. in einem anderen Gremium).
_GILT_ALS_BEHANDELT = re.compile(
    r"(?:gilt|gelten)\s+als\s+(?:behandelt|erledigt)|als\s+(?:behandelt|erledigt)\s+"
    r"(?:gelten|angesehen)|f[uü]r\s+erledigt", re.IGNORECASE)
_GILT_AM_ENDE = re.compile(r"(?:gilt|gelten)\s+als\s+(?:behandelt|erledigt)\W*$", re.IGNORECASE)
_VERWIESEN = re.compile(r"verwiesen|verweisung|vertagt|zur[uü]ckgestellt|abgesetzt|[uü]berwiesen",
                        re.IGNORECASE)
#: Wörter einer inhaltlichen Abstimmung. Steht eines im Satz neben der Formel,
#: ist nicht mehr eindeutig, was entschieden wurde — dann bleibt der Wert, den
#: das Modell gewählt hat („Beide Anträge gelten als behandelt", nachdem der
#: Vorschlag des OB angenommen wurde, 3478).
_ABSTIMMUNG = re.compile(r"abgelehnt|angenommen|beschlossen|beschließt|zugestimmt|stimmt\s+zu|ablehn|"
                         r"\blehnt\b.*\bab\b", re.IGNORECASE)
#: Ein abgelehnter Verweisungsantrag ist keine Verweisung („Der Ausschuss lehnt
#: den Verweisungsantrag der CDU mehrheitlich ab", 14874 auf Prod).
_ABGELEHNT = re.compile(r"abgelehnt|ablehn|\blehnt\b.*\bab\b", re.IGNORECASE)


def normalize_outcome(outcome: str | None, raw_result: str | None,
                      kind: str = "decision") -> str | None:
    """Das Ergebnis eines Hauptpunkts — der Original-Abstimmungssatz gewinnt.

    **Warum.** „gilt als behandelt" stand im Bestand verstreut auf
    ``no_decision`` (59), ``accepted`` (43), ``postponed`` (20) und ``noted`` (3):
    das Modell hörte das „einstimmig" des Verfahrensantrags und nahm den
    Inhalt für angenommen (Datensatz 19018: Schlossplatz-Spielplatz, „Frag den
    Rat" zitierte ihn als Auftrag). Das Ergebnis heißt jetzt ``settled``.
    Wird der Punkt dabei verwiesen oder vertagt, ist es ``postponed``.

    Nur Hauptpunkte: Ein Verfahrensantrag selbst (``subvote``) wird ja
    tatsächlich angenommen oder abgelehnt.
    """
    if kind != "decision" or not raw_result:
        return outcome
    text = " ".join(raw_result.split())
    if _GILT_ALS_BEHANDELT.search(text):
        if _VERWIESEN.search(text):
            return "postponed"
        if _GILT_AM_ENDE.search(text) or not _ABSTIMMUNG.search(text):
            return "settled"
        return outcome
    if outcome == "accepted" and _VERWIESEN.search(text) and not _ABGELEHNT.search(text):
        # „einstimmig … in den Ausschuss verwiesen": angenommen wurde die
        # Verweisung, nicht der Inhalt.
        return "postponed"
    return outcome


def normalize_vote(vote: str | None, raw_result: str | None) -> str | None:
    """``unanimous`` / ``majority`` / ``None`` — nie ein anderer Wert.

    Das Protokoll-Modell schrieb bis 09/2026 zwei Fehler in die Spalte:
    „einstimmig bei neun Enthaltungen" wurde ``majority`` (6444, 6606, 8426,
    9388 — Lotti las dann „mehrheitlich"), und zweimal stand der Satz selbst
    als Wert da (6929, 6930). Der Original-Abstimmungssatz ist die Quelle;
    er entscheidet, wo er eindeutig ist.
    """
    if raw_result and _EINSTIMMIG_MIT_ENTHALTUNGEN.match(raw_result):
        return "unanimous"
    if vote in VOTES:
        return vote
    low = (vote or "").strip().lower()
    if _EINSTIMMIG_MIT_ENTHALTUNGEN.match(low):
        return "unanimous"
    if low.startswith("mehrheitlich"):
        return "majority"
    return None
