"""„Lotti erklärt's einfach" (RL-904): Beschlusstexte in 2–3 bürgernahe Sätze.

Nur echte Beschlüsse (kind='decision') mit substanziellem Beschlusstext
(≥ 200 Zeichen) bekommen eine Kurzfassung; Auswahl + Persistenz übernimmt
``CouncilStore`` (decisions_needing_simple_summary / save_simple_summary).
Prompts liegen in nwz/prompts.py und sind über das Admin-UI editierbar.
"""
from __future__ import annotations

import json
import os

from nwz import llm, prompts

MODEL = os.environ.get("COUNCIL_SIMPLE_MODEL", "deepseek/deepseek-v4-pro")
# Beschlusstexte können sehr lang sein — fürs Erklären reicht der Anfang,
# und ein hartes Limit hält die Token-Kosten je Beschluss vorhersagbar.
MAX_BESCHLUSS_CHARS = 6000


def generate_one(decision: dict) -> str | None:
    """Kurzfassung für einen Beschluss-Dict (id/title/beschluss/committee/
    session_date). None = LLM-Antwort unbrauchbar; "" = bewusst keine
    Erklärung möglich (wird NICHT gespeichert, damit ein späterer Lauf mit
    besserem Prompt erneut ansetzt)."""
    system = prompts.get("simple_summary_system")
    user = prompts.render(
        "simple_summary_user",
        title=(decision.get("title") or "(ohne Titel)").strip(),
        committee=decision.get("committee") or "",
        session_date=decision.get("session_date") or "",
        beschluss=(decision.get("beschluss") or "")[:MAX_BESCHLUSS_CHARS],
    )
    try:
        resp = llm.chat_complete(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=400,
            temperature=0.3,
            _feature="simple_summary",
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception:  # noqa: BLE001 — Aufrufer entscheidet über Retry beim nächsten Lauf
        return None
    text = (data.get("einfach") or "").strip()
    # Plausibilitäts-Leitplanken: leere oder ausufernde Antworten verwerfen.
    if not text or len(text) > 700:
        return None
    return text
