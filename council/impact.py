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

from kern import llm, prompts

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


def _agenda_batch_text(items: list[dict]) -> str:
    """Ein Tagesordnungspunkt hat noch keinen Beschlusstext — dafür Signale,
    die das Modell selbst nicht kennen kann: wie oft dieselbe Formulierung
    schon dran war (Routine!), was beschlossen werden soll, was die Vorlage zu
    den Kosten sagt, durch wie viele Gremien sie geht."""
    lines: list[str] = []
    for it in items:
        wieder = int(it.get("wiederkehr") or 0)
        routine = ("erstmalig" if wieder <= 1 else
                   f"stand schon {wieder}× so auf einer Tagesordnung")
        signals = [
            f"Behandlung {it.get('behandlung') or 'unbekannt'}",
            f"Gremium {it.get('committee') or '?'}",
            f"Wiederkehr: {routine}",
        ]
        if it.get("antragsteller"):
            signals.append(f"Antrag von {it['antragsteller']}")
        if it.get("stationen"):
            signals.append(f"{it['stationen']} Stationen in der Beratungsfolge")
        if it.get("amt"):
            signals.append(f"Federführung {it['amt']}")
        teile = [f"id {it['id']}: {(it.get('title') or '').strip()}",
                 "  Signale: " + " · ".join(signals)]
        if it.get("beschlussvorschlag"):
            teile.append("  Soll beschlossen werden: "
                         + " ".join(str(it["beschlussvorschlag"]).split())[:500])
        if it.get("finanz_check"):
            teile.append("  Kosten laut Vorlage: "
                         + " ".join(str(it["finanz_check"]).split())[:280])
        text = (it.get("summary") or it.get("sachverhalt") or "").strip().replace("\n", " ")
        if text:
            teile.append(f"  Auszug: {text[:MAX_EXCERPT_CHARS]}")
        lines.append("\n".join(teile))
    return "\n\n".join(lines)


def rate_agenda_batch(items: list[dict]) -> list[tuple[int, int, str]]:
    """Bewertet Tagesordnungspunkte VOR der Sitzung → (id, score, warum).

    Eigener Prompt statt des Beschluss-Prompts (``top_wichtigkeit_*``): Vor der
    Sitzung gibt es keinen Beschlusstext, dafür Beschlussvorschlag, Kostenteil
    und — entscheidend — die Wiederkehr. „Annahme von Zuwendungen" stand 101×
    auf einer Tagesordnung; ohne dieses Signal hält jedes Modell den Punkt für
    eine Geldentscheidung (Tims Befund 15.08.). Der Grund kommt in einfacher
    Sprache zurück und steht so auf der Karte.
    """
    if not items:
        return []
    valid_ids = {it["id"] for it in items}
    system = prompts.get("top_wichtigkeit_system")
    user = prompts.render("top_wichtigkeit_user", batch=_agenda_batch_text(items))
    try:
        resp = llm.chat_complete(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=2600,
            temperature=0.1,
            _feature="impact_rating_agenda",
        )
        data = json.loads(resp.choices[0].message.content or "{}")
    except Exception:  # noqa: BLE001 — nächster Lauf versucht es erneut
        return []
    out: list[tuple[int, int, str]] = []
    for r in data.get("ratings") or []:
        try:
            iid = int(r.get("id"))
            score = int(r.get("score"))
        except (TypeError, ValueError):
            continue
        if iid in valid_ids and 0 <= score <= 100:
            warum = str(r.get("warum") or r.get("grund") or "").strip()
            out.append((iid, score, warum[:300]))
    return out


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
