"""Generate a short, neutral recap per policy field ("Was bewegte den Rat im Bereich X?").

For one policy field, takes its most recent decisions and asks the LLM for a compact
recap — one lead line plus 3–4 bullet points (the frontend renders them as a
scannable digest card; old prose recaps fall back to a paragraph). Owner-agnostic
like ``topics.py``; the offline cron (``scripts/generate_field_recaps.py``) stores
the result and the web service only ever reads it. The prompt template lives in
``nwz/prompts.py`` („recap_themenfeld") and is admin-editable.
"""
from __future__ import annotations

import logging
import os

from nwz import llm, prompts

MODEL = os.environ.get("COUNCIL_RECAP_MODEL", "deepseek/deepseek-v4-pro")

logger = logging.getLogger("council.recaps")


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
    """Return a recap for one field (lead line + "- "-bullets). Raises on an
    empty LLM reply."""
    prompt = prompts.render("recap_themenfeld", field=field_label, items=_render_items(decisions))
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
