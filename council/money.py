"""Extract euro amounts from council decision texts (heuristic, no LLM).

Conservative: only matches numbers paired with a currency token (€ / EUR / Euro),
so it doesn't pick up dates or counts. Handles German number formatting
(1.500.000,50) and Mio./Mrd. scaling. The "headline" amount of a decision is taken
as the largest extracted value — it's a scale indicator, not an exact budget figure.
"""
from __future__ import annotations

import re

_NUM = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?"
_CUR = r"(?:€|EUR|Euro)"
# "1,2 Mio. €" / "3 Millionen Euro" / "1,5 Mrd"
_SCALED = re.compile(rf"({_NUM})\s*(Mio\.?|Mrd\.?|Mill?\.?|Millionen|Milliarden)\s*{_CUR}?", re.IGNORECASE)
# Skip unit rates ("275 €/m²", "12 € pro Einwohner") — they aren't a decision's volume.
_UNIT = r"(?!\s*(?:/|pro\s+|je\s+)\s*(?:m²|m2|qm|quadratmeter|einwohner|kopf|person|stück|stunde))"
# "250.000 €" / "12.500,00 EUR" — non-letter lookahead (not \b, which fails after €)
_PLAIN = re.compile(rf"({_NUM})\s*{_CUR}(?![a-zA-Z]){_UNIT}", re.IGNORECASE)

_MAX = 5_000_000_000  # sanity ceiling (Oldenburg's budget is ~1 bn)


def _to_float(num: str) -> float | None:
    num = num.strip()
    num = num.replace(".", "").replace(",", ".") if "," in num else num.replace(".", "")
    try:
        return float(num)
    except ValueError:
        return None


def _scale(unit: str) -> float:
    u = unit.lower()
    return 1e9 if (u.startswith("mrd") or "milliard" in u) else 1e6


def extract_amounts(text: str) -> list[float]:
    """All euro amounts found in ``text`` (within a sane range)."""
    if not text:
        return []
    out: list[float] = []
    for m in _SCALED.finditer(text):
        v = _to_float(m.group(1))
        if v is not None:
            out.append(v * _scale(m.group(2)))
    for m in _PLAIN.finditer(text):
        v = _to_float(m.group(1))
        if v is not None:
            out.append(v)
    return [a for a in out if 0 < a < _MAX]


def largest_amount(text: str) -> float | None:
    """The largest euro amount in the text (a decision's headline financial volume)."""
    amounts = extract_amounts(text)
    return max(amounts) if amounts else None
