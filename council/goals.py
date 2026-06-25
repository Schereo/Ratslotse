"""Track council decisions against the city's overarching goals.

Each goal has keywords (for candidate retrieval) and a description (for the LLM).
``assess_batch`` asks the LLM, per candidate decision, whether it really concerns
the goal and whether it advances / hinders / is neutral toward it. This is honest
about what it measures: council *activity and direction* on a goal, not a real-world
KPI (e.g. actual CO₂ tonnes).

Retrieval is keyword-based for now; semantic embedding retrieval is the planned
upgrade (see council-ai-roadmap).
"""
from __future__ import annotations

import json
import os

from nwz import llm
from council.topics import _strip_fences

MODEL = os.environ.get("COUNCIL_GOAL_MODEL", "deepseek/deepseek-v4-pro")

# key -> {label, description, keywords}. User-extensible config.
GOALS: dict[str, dict] = {
    # Grounded in Oldenburg's actual plans (oldenburg.de), 2026-06.
    "klima_2035": {
        "label": "Klimaneutralität 2035",
        "description": "Ratsbeschluss vom April 2021: Oldenburg soll bis 2035 klimaneutral werden. "
                       "Zentrales Instrument ist der Klimaschutzplan Oldenburg 2035 mit 90 Maßnahmen, "
                       "Schwerpunkt Gebäude/Strom/Wärme; Vermeidung und Verminderung von Treibhausgasen vor Kompensation.",
        "keywords": ["klimaneutral", "klimaschutz", "klimaschutzplan", "klimaziel", "CO2", "treibhausgas",
                     "erneuerbar", "photovoltaik", "solar", "windkraft", "wärmewende", "wärmeplanung",
                     "fernwärme", "energetische sanierung", "klimaanpassung"],
    },
    "verkehrswende": {
        "label": "Mobilitätsplan 2030 (Verkehrswende)",
        "description": "Mobilitätsplan Oldenburg 2030 (Ratsbeschluss Juni 2023, Motto: 100 Prozent fürs Klima): "
                       "nachhaltige Mobilität bis 2030 mit zwölf Teilkonzepten — Radverkehrs-Premiumnetz, Fahrradstraßen/-zonen, "
                       "durchgängige ÖPNV-Spur am Wallring, Mobilstationen, E-Ladeinfrastruktur, Parkraummanagement, Park&Ride.",
        "keywords": ["radverkehr", "radweg", "fahrradstraße", "fahrradzone", "premiumnetz", "fahrrad",
                     "öpnv", "busspur", "wallring", "mobilitätsstation", "ladeinfrastruktur", "tempo 30",
                     "fußverkehr", "verkehrswende", "parkraummanagement", "park&ride", "modal split",
                     "verkehrsfläche", "parkhaus", "stellplatz"],
    },
    "wohnungsbau": {
        "label": "Bezahlbarer Wohnraum",
        "description": "Schaffung und Erhalt von bezahlbarem Mietwohnraum (städtisches Wohnungsbauförderungs"
                       "programm, Arbeitskreis Bündnis Wohnen in Oldenburg): preisgünstiger Neubau, "
                       "sozialer Wohnungsbau, Nachverdichtung, neue Wohnquartiere.",
        "keywords": ["wohnungsbau", "wohnungsbauförderung", "bündnis wohnen", "wohnraum", "mietwohnraum",
                     "preisgünstig", "sozialwohnung", "sozialer wohnungsbau", "bebauungsplan",
                     "wohnquartier", "nachverdichtung", "baulandentwicklung"],
    },
    "bildung_betreuung": {
        "label": "Kita- & Schulausbau",
        "description": "Ausbau von Kinderbetreuung und Schulen: neue Kitas, Krippenplätze, "
                       "Ganztag, Schulsanierung und -neubau.",
        "keywords": ["kita", "kindertagesstätte", "krippe", "kinderbetreuung", "ganztag",
                     "schulneubau", "schulsanierung", "grundschule", "betreuungsplatz"],
    },
    "innenstadt": {
        "label": "Innenstadtstrategie",
        "description": "Innenstadtstrategie (Arbeitskreis Bündnis Innenstadt, 2020): Stärkung der Innenstadt — "
                       "Einzelhandel, Aufenthaltsqualität, gegen Leerstand, Fußgängerzone, Märkte und Veranstaltungen.",
        "keywords": ["innenstadt", "innenstadtstrategie", "bündnis innenstadt", "fußgängerzone", "einzelhandel",
                     "leerstand", "aufenthaltsqualität", "wochenmarkt", "innenstadtentwicklung"],
    },
    "digitalisierung": {
        "label": "Digitalisierungsstrategie & Smart City",
        "description": "Digitalisierungsstrategie (Stadtrat Dezember 2023): Transparenz, Effizienz und IT-Sicherheit, "
                       "Optimierung von Verwaltungsprozessen, Stärkung der Bürgerbeteiligung; Smart City Oldenburg.",
        "keywords": ["digital", "digitalisierungsstrategie", "smart city", "online-dienst", "e-government",
                     "verwaltungsprozess", "bürgerbeteiligung", "it-sicherheit", "breitband", "glasfaser"],
    },
}

STANCES = ("voran", "bremst", "neutral")

_PROMPT = """Du bewertest, ob Beschlüsse des Oldenburger Stadtrats ein übergeordnetes Ziel betreffen und ob sie es voranbringen.

ZIEL: {label}
{description}

Für JEDEN Beschluss liefere:
- "relevant": true NUR wenn der Beschluss das Ziel konkret betrifft, sonst false
- "stance": wenn relevant — "voran" (bringt das Ziel voran), "bremst" (wirkt entgegen) oder "neutral" (betrifft es, aber neutral/gemischt); sonst "neutral"
- "grund": max. ein kurzer Satz (deutsch)

Antworte mit NUR JSON: {{"results": [{{"id": <id>, "relevant": <true|false>, "stance": "<voran|bremst|neutral>", "grund": "..."}}]}}
Regeln:
- jede vorgelegte id genau einmal mit exakt dieser id; im Zweifel relevant=false.
- Der Ausgang steht in [eckigen Klammern]. Beschlüsse, die nur ZUR KENNTNIS genommen
  wurden (Berichte, [zur_kenntnis]) oder VERTAGT sind ([vertagt]), bringen das Ziel
  NICHT voran → "neutral" — AUSSER der Text dokumentiert konkret bereits umgesetzten
  oder beschlossenen Fortschritt. Reine Sachstands-/Prüfberichte, Absichts­erklärungen
  und Resolutionen sind "neutral". "voran" nur bei einem tatsächlich gefassten,
  zielfördernden Beschluss ([angenommen]).

BESCHLÜSSE:
{items}"""


def _render(decisions: list[dict]) -> str:
    lines = []
    for d in decisions:
        text = d.get("summary") or d.get("beschluss") or ""
        text = " ".join(text.split())[:300]
        outcome = d.get("outcome") or "?"
        lines.append(f'- id {d["id"]} [{outcome}]: {(d.get("title") or "").strip()} — {text}')
    return "\n".join(lines)


def assess_batch(goal_key: str, decisions: list[dict], model: str = MODEL):
    """One LLM call rating a batch of candidates for a goal.
    Returns ``(results_by_id, usage)`` with id -> {relevant, stance, grund}."""
    goal = GOALS[goal_key]
    prompt = _PROMPT.format(label=goal["label"], description=goal["description"], items=_render(decisions))
    extra = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    messages = [{"role": "user", "content": prompt}]
    valid = {d["id"] for d in decisions}
    last_err: Exception = ValueError("no response")
    for _ in range(2):
        resp = llm.chat_complete(model=model, temperature=0, response_format={"type": "json_object"},
                                 max_tokens=4000, messages=messages, **extra)
        content = _strip_fences(resp.choices[0].message.content or "")
        if not content:
            last_err = ValueError("empty LLM response")
            continue
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            last_err = exc
            continue
        out: dict[int, dict] = {}
        for r in data.get("results", []):
            try:
                rid = int(r["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if rid not in valid:
                continue
            relevant = bool(r.get("relevant"))
            stance = r.get("stance") if r.get("stance") in STANCES else "neutral"
            out[rid] = {"relevant": relevant, "stance": stance, "grund": (r.get("grund") or "").strip()[:200]}
        if out:
            return out, resp.usage
        last_err = ValueError("no valid results")
    raise last_err
