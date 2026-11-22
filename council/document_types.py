"""Welche Art Dokument eine Unterlage ist — aus Label und Textkopf, ohne Modell.

Grundlage der Gegenlese-Liste und des Dossiers (docs/plan-vorlagen-aufbereiten.md,
§ 3.1 und § 5): Anträge zuerst, dann Synopse und Satzung, dann der Rest. Das
Label allein reicht nicht — „2026-10-31 Reduzierung Anzahl beratende Mitglieder"
ist ein Änderungsantrag der Grünen, das sagt erst die erste Seite.

Die Reihenfolge der Regeln ist die Rangfolge: Ein „Änderungsantrag zur
Satzung" ist ein Änderungsantrag, keine Satzung.
"""
from __future__ import annotations

import re
from typing import Literal

DocType = Literal["template", "amendment", "motion", "report_request", "synopsis", "statute",
                  "plan", "statement", "objection_table", "audit_report", "report", "presentation", "other"]

#: Reihenfolge in der Gegenlese-Liste (§ 6.1, Punkt 4).
ORDER: tuple[DocType, ...] = ("template", "amendment", "motion", "report_request", "synopsis",
                              "statute", "statement", "objection_table", "audit_report", "plan", "report",
                              "presentation", "other")

KOPF_ZEICHEN = 1_500

_LABEL: list[tuple[DocType, re.Pattern]] = [
    ("template", re.compile(r"^\s*vorlage(?:\s+\d\d[/ ]\d{4}(?:/\d+)?)?\s*$", re.I)),
    ("amendment", re.compile(r"(?:ä|ae|a)nderungsantr[aä]g|ergänzungsantr[aä]g|zusatzantr[aä]g|"
                             r"gegenantr[aä]g", re.I)),
    ("report_request", re.compile(r"berichtsantr[aä]g|\banfrage", re.I)),
    ("motion", re.compile(r"\b(?:dringlichkeits|fraktions|beschluss|verweisungs)?antr[aä]g", re.I)),
    # Vor Synopse und Stellungnahme: „Abwägungssynopse" ist eine Abwägung, und
    # die Abwägung der Stellungnahmen liest ein eigener Leser (council/spezialleser.py).
    ("objection_table", re.compile(r"abwägung|prüfung\s+der\s+stellungnahmen", re.I)),
    # Vor „bericht": der Schlussbericht des Rechnungsprüfungsamts mit Prüfvermerken.
    ("audit_report", re.compile(r"rechnungsprüfungsamt|schlussbericht\s+(?:des|über|zum)", re.I)),
    ("synopsis", re.compile(r"synopse|gegenüberstellung|alt\s*(?:/|und|–|-)\s*neu|lesefassung|änderungsliste", re.I)),
    ("statute", re.compile(r"satzung|geschäftsordnung|richtlinie|verordnung|entgeltordnung|gebührenordnung|"
                           r"\bordnung\b|vertrag\b|vereinbarung", re.I)),
    ("statement", re.compile(r"stellungnahme|erläuterung|einwendung|anregungen", re.I)),
    ("plan", re.compile(r"bebauungsplan|planzeichnung|lageplan|übersichtsplan|\bkarte\b|\bplan\s*\d|"
                        r"geltungsbereich|flächennutzungsplan|leitplan|gestaltungsplan|lupenpl|planversand|"
                        r"vorbehaltsnetz|\bfotos?\b", re.I)),
    ("report", re.compile(r"bericht|gutach|studie|konzept|jahresabschluss|lagebericht|prüf|"
                          r"evaluation|analyse|statistik|übersicht|auswertung|wirtschaftsplan|begründung|"
                          r"untersuchung|fachbeitrag|bilanz|gewinn-\s*und\s*verlust|\bguv\b|bestandserfassung|"
                          r"kampfmittel|archäolog|liste\b|protokoll|investitionsprogramm|\bthh|budget|"
                          r"laborergebnis|exposé|grundzüge", re.I)),
    ("presentation", re.compile(r"präsentation|vortrag|folien|praesentation", re.I)),
]

_KOPF_AENDERUNG = re.compile(
    r"(?:Änderungs|Aenderungs|Ergänzungs|Zusatz)antrag|beantrag\w*\b[^.]{0,120}\bfolgende\w*\s+Änderung",
    re.I)
_KOPF_ANTRAG = re.compile(r"\b(?:Dringlichkeits|Fraktions|Beschluss)?antrag\b|\bbeantrag(?:en|t)\b", re.I)
_KOPF_BERICHT = re.compile(r"Berichtsantrag|bitten\s+(?:die\s+)?Verwaltung[^.]{0,80}\bzu\s+berichten", re.I)


def classify(label: str | None, text: str | None = None) -> DocType:
    """Art des Dokuments aus dem Label, sonst aus dem Kopf des Textes."""
    lab = (label or "").strip()
    kopf = (text or "")[:KOPF_ZEICHEN]
    for art, muster in _LABEL:
        if muster.search(lab):
            # „2026 11 01. - Antrag Änderung Geschäftsordnung §24" ist laut
            # Kopf ein Änderungsantrag (Volt) — der Text präzisiert das Label.
            if art == "motion" and kopf and _KOPF_AENDERUNG.search(kopf):
                return "amendment"
            return art
    if kopf:
        if _KOPF_AENDERUNG.search(kopf):
            return "amendment"
        if _KOPF_BERICHT.search(kopf):
            return "report_request"
        if _KOPF_ANTRAG.search(kopf[:600]):
            return "motion"
    return "other"


def rank(art: str) -> int:
    return ORDER.index(art) if art in ORDER else len(ORDER)  # type: ignore[arg-type]
