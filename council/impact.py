"""Tragweite-Score (RL-U16): Wie folgenreich ist ein Beschluss?

Das Gegenstück zum Interessantheits-Score (``council/interest.py``): Der
belohnt Kuriosität (schräge Straßennamen landen oben) und taugt darum nicht
als Priorität. Hier bewertet ein LLM die TRAGWEITE nach fester Rubrik
(Betroffene · Geld · Bindungswirkung · Präzedenz, je 0–25) mit
Anker-Beispielen zur Kalibrierung — die Lehre aus dem Interest-Lauf. Der
Batch bekommt Struktur-Signale (kind, outcome, Betrag, Gremium, Textlänge)
mit, nicht nur Titel. Das Ergebnis mischt 50/50 in den Wichtig-Wert
(``CouncilStore.backfill_importance``); die Heuristik bleibt der Boden.
Vor dem Prod-Rollout: ``scripts/eval_impact.py`` gegen das Golden-Set.
"""
from __future__ import annotations

import json
import os

from nwz import llm, prompts

MODEL = os.environ.get("COUNCIL_IMPACT_MODEL", "deepseek/deepseek-v4-pro")
BATCH_SIZE = 20
MAX_EXCERPT_CHARS = 600


def _batch_text(decisions: list[dict]) -> str:
    lines: list[str] = []
    for d in decisions:
        text = (d.get("beschluss") or d.get("summary") or "").strip().replace("\n", " ")
        amount = d.get("amount_eur")
        signals = (
            f"Art {d.get('kind') or 'decision'} · Ergebnis {d.get('outcome') or '?'} · "
            f"Gremium {d.get('committee') or '?'} · "
            f"Betrag {f'{amount:,.0f} €'.replace(',', '.') if amount else 'keiner genannt'} · "
            f"Beschlusstext {len(d.get('beschluss') or '')} Zeichen"
        )
        lines.append(
            f"id {d['id']}: {(d.get('title') or '').strip()}\n"
            f"  Signale: {signals}\n"
            f"  Auszug: {text[:MAX_EXCERPT_CHARS]}"
        )
    return "\n\n".join(lines)


def rate_batch(decisions: list[dict]) -> list[tuple[int, int, str]]:
    """Bewertet einen Batch → Liste (decision_id, impact 0–100, grund).
    Halluzinierte IDs und Out-of-range-Scores werden verworfen."""
    if not decisions:
        return []
    valid_ids = {d["id"] for d in decisions}
    system = prompts.get("impact_bewertung_system")
    user = prompts.render("impact_bewertung_user", batch=_batch_text(decisions))
    try:
        resp = llm.chat_complete(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=2200,
            temperature=0.1,
            _feature="impact_rating",
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
