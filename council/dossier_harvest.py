"""Vor-Ernte für das Dossier, ohne Modell (docs/plan-vorlagen-aufbereiten.md § 4.1).

- **Form** (F1–F8, § 2.3) aus Vorlagenart, Titelendung und den Typen der
  Anlagen. Das Modell bekommt nur das Schema seiner Form.
- **Kandidaten** mit Seite: Beträge, Daten, Paragrafen — als feste Fakten im
  Prompt, und ein Betrag oder Datum im Dossier muss unter ihnen stehen.
"""
from __future__ import annotations

import re

from council import unterlagen_seiten

FORMEN = {
    "F1": "Formalie (Widmung, Benennung, Zuwendung, Besetzung)",
    "F2": "Sachentscheidung (Bau, Investition, Grundlagenbeschluss)",
    "F3": "Regelwerk (Satzung, Geschäftsordnung, Gebühren)",
    "F4": "Geld (über-/außerplanmäßig, Jahresabschluss)",
    "F5": "Bauleitplanung",
    "F6": "Antrag (Fraktionsantrag mit Stellungnahme, Dringlichkeitsantrag)",
    "F7": "Bericht oder Anfrage",
    "F8": "Einzelfall (Einsprüche, Widersprüche)",
}

_F = [
    ("F5", re.compile(r"bebauungsplan|flächennutzungsplan|veränderungssperre|bauleitplan", re.I)),
    ("F8", re.compile(r"einspr(?:uch|üche)|widersprüche?\b", re.I)),
    ("F4", re.compile(r"überplanmäßig|außerplanmäßig|jahresabschluss|lagebericht|haushaltssatzung|nachtragshaushalt|"
                      r"mehraufwendungen|mehrauszahlungen|bürgschaft", re.I)),
    ("F3", re.compile(r"satzung|geschäftsordnung|gebührenordnung|entgeltordnung|richtlinie|verordnung", re.I)),
    ("F1", re.compile(r"widmung|benennung|besetzung|zuwendungen|beratende mitglieder|ausschüsse|wahl d|"
                      r"berufung|vertreter", re.I)),
]

_BETRAG_RE = re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+(?:,\d+)?\s*(?:€|Euro|EUR)|\d+(?:,\d+)?\s*(?:Mio\.?|Millionen)\s*(?:€|Euro)?|"
                        r"\d+(?:,\d{2})\s*(?:€|Euro)|\d+\s*(?:€|Euro)\b", re.I)
_DATUM_RE = re.compile(r"\b\d{1,2}\.\s?\d{1,2}\.\s?(?:19|20)\d{2}\b|\b\d{1,2}\.\s+(?:Januar|Februar|März|April|Mai|Juni|Juli|"
                       r"August|September|Oktober|November|Dezember)\s+(?:19|20)\d{2}\b")
_PARAGRAF_RE = re.compile(r"§\s*\d+[a-z]?(?:\s*Abs(?:atz|\.)\s*\d+)?(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß]+G)?")


def form(title: str | None, kind: str | None, doc_types: list[str]) -> str | None:
    """Die Form einer Vorlage — ``None``, wenn sie in keine passt (dann nur der Kern)."""
    t = f"{title or ''}"
    if re.search(r"bericht\s*$|berichtsantrag|anfrage|sachstand", t, re.I) or (kind or "").lower().startswith("bericht"):
        return "F7"
    for f, muster in _F:
        if muster.search(t):
            return f
    if re.search(r"beschlussantrag|dringlichkeitsantrag|antrag\b", t, re.I):
        return "F6"
    if "statute" in doc_types or "synopsis" in doc_types:
        return "F3"
    if re.search(r"beschluss\s*$", t, re.I):
        return "F2"
    return None


def candidates(text: str, offsets: list[int] | None) -> dict[str, list[dict]]:
    """Beträge, Daten und Paragrafen mit Seite — ohne Dubletten, in Textfolge."""
    out: dict[str, list[dict]] = {"amounts": [], "dates": [], "paragraphs": []}
    for key, muster in (("amounts", _BETRAG_RE), ("dates", _DATUM_RE), ("paragraphs", _PARAGRAF_RE)):
        gesehen = set()
        for m in muster.finditer(text or ""):
            wert = re.sub(r"\s+", " ", m.group(0)).strip()
            if wert in gesehen:
                continue
            gesehen.add(wert)
            out[key].append({"value": wert, "page": unterlagen_seiten.page_of(offsets, m.start())})
            if len(out[key]) >= 25:
                break
    return out
