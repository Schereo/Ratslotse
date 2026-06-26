"""Generate a short, neutral recap per policy field ("Was bewegte den Rat im Bereich X?").

For one policy field, takes its most recent decisions and asks the LLM for a compact
3–5 sentence prose recap — the plain-language "executive summary" behind the trend
charts. Owner-agnostic like ``topics.py``; the offline cron
(``scripts/generate_field_recaps.py``) stores the result and the web service only
ever reads it.
"""
from __future__ import annotations

import logging
import os

from nwz import llm

MODEL = os.environ.get("COUNCIL_RECAP_MODEL", "deepseek/deepseek-v4-pro")

logger = logging.getLogger("council.recaps")

_PROMPT = """Du schreibst einen kurzen, neutralen Rückblick für die Bürger:innen Oldenburgs:
Was hat den Stadtrat im Themenfeld „{field}" zuletzt beschäftigt?

Hier die jüngsten Beschlüsse/Berichte in diesem Feld (neueste zuerst):
{items}

Schreibe 3–5 Sätze in klarem, gut lesbarem Deutsch:
- Welche Schwerpunkte, Projekte oder Entscheidungen prägen das Feld aktuell?
- Nenne konkrete Vorhaben/Orte, wenn sie in den Einträgen vorkommen.
- Neutral und sachlich: keine Wertung, keine Partei-Bewertung, keine Empfehlungen.
- Erfinde nichts; stütze dich ausschließlich auf die vorgelegten Einträge.
- Kein Markdown, keine Aufzählung — zusammenhängender Fließtext. Beginne direkt mit dem
  Inhalt (nicht mit „Im Themenfeld …")."""


def _render_items(decisions: list[dict]) -> str:
    lines = []
    for d in decisions:
        date = (d.get("session_date") or "")[:10]
        title = (d.get("title") or "").strip()
        summary = (d.get("summary") or "").strip()
        if not summary:
            summary = " ".join((d.get("beschluss") or "").split())[:200]
        outcome = d.get("outcome") or ""
        head = f"- {date} [{outcome}] {title}".rstrip()
        lines.append(head + (f" — {summary}" if summary else ""))
    return "\n".join(lines)


def generate_recap(field_label: str, decisions: list[dict], model: str = MODEL) -> str:
    """Return a 3–5 sentence prose recap for one field. Raises on an empty LLM reply."""
    prompt = _PROMPT.format(field=field_label, items=_render_items(decisions))
    extra: dict = {}
    if "deepseek" in model:
        extra = {"extra_body": {"reasoning": {"enabled": False}}}
    resp = llm.chat_complete(
        model=model, _feature="themenfeld_rueckblick", temperature=0.3,
        max_tokens=600, messages=[{"role": "user", "content": prompt}], **extra,
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise ValueError("empty LLM response")
    return text
