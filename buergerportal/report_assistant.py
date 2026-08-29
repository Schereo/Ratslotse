"""Datenminimierung für die optionale KI-Schreibhilfe privater Meldungen.

Der Assistent erhält weder Konto- noch Kartenangaben. Freitext wird lokal um
häufige direkte Identifikatoren bereinigt, bevor er den zentral konfigurierten
No-Training-/ZDR-LLM-Pfad erreicht. Der vollständige bestätigte Meldetext wird
weiterhin ausschließlich lokal als private Meldung gespeichert.
"""
from __future__ import annotations

import re

_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
_HANDLE = re.compile(r"(?<!\w)@[A-Za-z0-9_.-]{2,}")
_ADDRESS = re.compile(
    r"\b[A-ZÄÖÜ][\wÄÖÜäöüß.-]*(?:straße|str\.|weg|allee|platz|ring|damm|ufer|chaussee)"
    r"\s+\d{1,4}[a-z]?(?=\s|[,.!?;:]|$)",
    re.IGNORECASE,
)
_NAMED_PERSON = re.compile(
    r"(?i)\b(?:Herrn?|Frau|Dr\.?|Prof\.?)\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'-]{1,60}\b"
)
_SELF_NAMED = re.compile(
    r"(?i)\b(?:mein Name ist|ich heiße)\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'-]+"
    r"(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß'-]+)?\b"
)
_POSTCODE = re.compile(r"\b\d{5}\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß.-]+\b")
_PHONE_CANDIDATE = re.compile(r"(?<!\w)(?:\+?\d[\d ()/.-]{5,}\d)(?!\w)")


def _redact_phone(match: re.Match[str]) -> str:
    value = match.group(0)
    return "[TELEFON ENTFERNT]" if sum(character.isdigit() for character in value) >= 6 else value


def redact_personal_data(value: str) -> tuple[str, bool]:
    """Remove common direct identifiers without transmitting the original.

    This deliberately runs before prompt construction. It is a narrow safety
    boundary, not a claim that arbitrary prose can be anonymised perfectly;
    the UI therefore also asks people not to enter names or contact details.
    """
    cleaned = " ".join(value.replace("\x00", " ").split())
    replacements = (
        (_EMAIL, "[E-MAIL ENTFERNT]"),
        (_URL, "[LINK ENTFERNT]"),
        (_HANDLE, "[NUTZERNAME ENTFERNT]"),
        (_ADDRESS, "[ADRESSE ENTFERNT]"),
        (_POSTCODE, "[ADRESSE ENTFERNT]"),
        (_NAMED_PERSON, "[NAME ENTFERNT]"),
        (_SELF_NAMED, "[NAME ENTFERNT]"),
    )
    redacted = False
    for pattern, replacement in replacements:
        next_value, count = pattern.subn(replacement, cleaned)
        redacted = redacted or count > 0
        cleaned = next_value
    next_value = _PHONE_CANDIDATE.sub(_redact_phone, cleaned)
    redacted = redacted or next_value != cleaned
    return next_value, redacted
