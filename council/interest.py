"""Interessantheits-Score (RL-U11): Wie erzählenswert ist ein Beschluss?

Bewusst getrennt vom Wichtigkeits-Score (``council/importance.py``): Der misst
Tragweite (Geld, Umstrittenheit, Ebene) als billige Heuristik — hier bewertet
ein LLM den GESPRÄCHSWERT für normale Stadtbewohner:innen (Kuriosität,
Alltagsnähe, Konkretheit). Der Score speist das „Fundstück des Tages"
(``council/fundstueck.py``) und ist per Backfill über den ganzen Bestand
berechenbar (``scripts/rate_interest.py``). Prompts in ``nwz/prompts.py``,
über das Admin-UI editierbar.
"""
from __future__ import annotations

import json
import os

from nwz import llm, prompts

MODEL = os.environ.get("COUNCIL_INTEREST_MODEL", "deepseek/deepseek-v4-pro")
# Batch-Bewertung: mehrere Beschlüsse je Call — kompakt, deterministisch
# genug bei niedriger Temperatur, und um Größenordnungen billiger als einzeln.
BATCH_SIZE = 20
MAX_EXCERPT_CHARS = 500


def _batch_text(decisions: list[dict]) -> str:
    lines: list[str] = []
    for d in decisions:
        excerpt = (d.get("beschluss") or d.get("summary") or "").strip().replace("\n", " ")
        lines.append(
            f"id {d['id']}: [{d.get('session_date', '?')}, {d.get('committee', '?')}, "
            f"Ergebnis {d.get('outcome') or '?'}] {(d.get('title') or '').strip()}\n"
            f"  Auszug: {excerpt[:MAX_EXCERPT_CHARS]}"
        )
    return "\n\n".join(lines)


def rate_batch(decisions: list[dict]) -> list[tuple[int, int, str]]:
    """Bewertet einen Batch → Liste (decision_id, score 0–100, grund).
    Liefert nur Einträge, deren id im Batch vorkam (LLM-Halluzinationen
    werden verworfen); bei kaputter Antwort eine leere Liste."""
    if not decisions:
        return []
    valid_ids = {d["id"] for d in decisions}
    system = prompts.get("interest_bewertung_system")
    user = prompts.render("interest_bewertung_user", batch=_batch_text(decisions))
    try:
        resp = llm.chat_complete(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=2000,
            temperature=0.2,
            _feature="interest_rating",
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception:  # noqa: BLE001 — nächster Lauf versucht es erneut
        return []
    out: list[tuple[int, int, str]] = []
    for r in data.get("ratings") or []:
        try:
            did = int(r.get("id"))
            score = int(r.get("score"))
        except (TypeError, ValueError):
            continue
        if did in valid_ids and 0 <= score <= 100:
            out.append((did, score, str(r.get("grund") or "").strip()[:300]))
    return out
