"""Fundstück des Tages (RL-U11, Design 10a): der tägliche Öffnungsgrund.

Kuratiert je Kalendertag EINEN erzählenswerten Beschluss aus dem Archiv:
Jahrestage („Heute vor N Jahren") gewinnen; sonst der interessanteste noch
nicht kürzlich gezeigte Fund (Interest-Score aus ``council/interest.py``).
Ein LLM schreibt die 1-Satz-Story; ohne brauchbare Story gibt es für den Tag
schlicht keine Karte (das Frontend lässt sie dann ersatzlos weg).
Karten werden Tage im Voraus generiert (``scripts/generate_fundstuecke.py``)
und liegen prüfbar in ``council_fundstuecke``.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date

from nwz import llm, prompts

from .store import CouncilStore

MODEL = os.environ.get("COUNCIL_FUNDSTUECK_MODEL", "deepseek/deepseek-v4-pro")
MIN_INTEREST_ANNIVERSARY = 45   # Jahrestag zählt nur, wenn der Fund selbst was hergibt
MIN_INTEREST_ARCHIVE = 60       # Archiv-Funde ohne Datumshaken müssen stärker sein
REUSE_BLOCK_DAYS = 180
MAX_BESCHLUSS_CHARS = 4000


def pick_candidate(store: CouncilStore, day: date) -> tuple[dict, int] | None:
    """Wählt den Beschluss für ``day`` → (decision, years_ago); years_ago 0 =
    kein Jahrestag. Deterministisch je Tag (Hash-Seed statt Zufall — Läufe
    sind wiederholbar, Resume-sicher und redaktionell nachvollziehbar)."""
    used = store.recent_fundstueck_decision_ids(REUSE_BLOCK_DAYS)

    # 1) Jahrestag: gleicher Kalendertag, früheres Jahr, brauchbarer Score.
    mmdd = day.strftime("%m-%d")
    for c in store.fundstueck_candidates(mmdd=mmdd, exclude_ids=used, limit=5):
        if (c.get("interest") or 0) < MIN_INTEREST_ANNIVERSARY:
            continue
        years = day.year - int(str(c["session_date"])[:4])
        if years >= 1:
            return c, years

    # 2) Archiv-Fund: unter den Top-Kandidaten deterministisch je Tag streuen,
    #    damit nicht wochenlang derselbe Spitzenreiter wartet, falls ein Lauf
    #    Tage überspringt.
    top = [
        c for c in store.fundstueck_candidates(exclude_ids=used, limit=10)
        if (c.get("interest") or 0) >= MIN_INTEREST_ARCHIVE
    ]
    if not top:
        return None
    seed = int(hashlib.sha256(day.isoformat().encode()).hexdigest(), 16)
    return top[seed % len(top)], 0


def write_story(decision: dict) -> str | None:
    """Der eine Satz der Karte. None = Antwort unbrauchbar (Tag bleibt leer)."""
    system = prompts.get("fundstueck_story_system")
    user = prompts.render(
        "fundstueck_story_user",
        session_date=str(decision.get("session_date") or ""),
        committee=decision.get("committee") or "",
        outcome=decision.get("outcome") or "unbekannt",
        title=(decision.get("title") or "").strip(),
        interest_reason=decision.get("interest_reason") or "",
        beschluss=(decision.get("beschluss") or decision.get("summary") or "")[:MAX_BESCHLUSS_CHARS],
    )
    try:
        resp = llm.chat_complete(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=300,
            temperature=0.4,
            _feature="fundstueck_story",
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception:  # noqa: BLE001 — nächster Lauf füllt den Tag erneut
        return None
    story = (data.get("story") or "").strip()
    if not story or len(story) > 260:
        return None
    return story


def kicker_for(years_ago: int) -> str:
    if years_ago == 1:
        return "Heute vor einem Jahr"
    if years_ago > 1:
        return f"Heute vor {years_ago} Jahren"
    return "Aus dem Archiv"


def generate_for_day(store: CouncilStore, day: date) -> bool:
    """Erzeugt (falls möglich) das Fundstück für einen Tag. True = gespeichert."""
    picked = pick_candidate(store, day)
    if not picked:
        return False
    decision, years = picked
    # interest_reason für den Story-Prompt nachladen (Kandidaten-Query ist schlank).
    full = store.get_decision(decision["id"]) or decision
    full.setdefault("committee", decision.get("committee"))
    full.setdefault("session_date", decision.get("session_date"))
    story = write_story(full)
    if not story:
        return False
    store.save_fundstueck(day.isoformat(), decision["id"], kicker_for(years), story)
    return True
