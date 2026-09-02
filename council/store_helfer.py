"""Drei kleine Helfer, die mehrere Ecken des Stores brauchen.

Sie standen bis 02.09.2026 auf Modulebene in ``store.py``. Beim sechsten
Schnitt fiel auf, warum das nicht bleiben kann: Ein Mixin in einer eigenen
Datei kann sie nicht aus ``store.py`` importieren — das wäre ein Ring, denn
``store.py`` importiert das Mixin.

Hier ist der gemeinsame Nenner. Bewusst klein und ohne Zustand: Was hier
hereinwandert, gehört keiner Ecke.
"""
from __future__ import annotations

import re


def _norm_title(t: str) -> str:
    """Normalised title for dedup: drops amounts, years, doc-suffixes and punctuation
    so the same matter across committees ('… - Beschluss' vs '…') and recurring series
    ('… 11.716.000 Euro …' vs '… 10.632.200 Euro …') collapse to one key."""
    t = (t or "").lower()
    t = re.sub(r"[\d.,]+", " ", t)  # amounts, years, budget numbers
    t = re.sub(r"\b(euro|eur|mio|mrd|beschluss|bericht|antrag|vorlage)\b", " ", t)
    t = re.sub(r"[^a-zäöüß ]", " ", t)  # punctuation, €, dashes
    return re.sub(r"\s+", " ", t).strip()

def _dedup_keys(title: str, template_number, decision_id: int) -> list[str]:
    """Collapse keys for a decision: the base Vorlage-Nr (strongest signal — same
    matter across committees/revisions, '22/0348' == '22/0348/1', and robust to title
    spelling variants) and the normalised title (catches recurring series under
    different Vorlagen). Two rows collapse if they share EITHER. Short/sparse titles
    fall back to the id so distinct tiny-title decisions are never merged."""
    keys: list[str] = []
    if template_number and str(template_number).strip():
        # Keep the base Vorlage (first two segments): "22/0348/1" → "22/0348".
        keys.append("v:" + "/".join(str(template_number).strip().split("/")[:2]))
    nt = _norm_title(title)
    keys.append("t:" + nt if len(nt) >= 12 else f"\x00id{decision_id}")
    return keys

def _int_or_none(v) -> int | None:
    """Coerce an LLM value to int, tolerating strings/None/non-numerics."""
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
