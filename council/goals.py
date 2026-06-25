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
    "klima_2035": {
        "label": "Klimaneutralität 2035",
        "description": "Das Ziel der Stadt Oldenburg, bis 2035 klimaneutral zu werden: "
                       "Treibhausgase senken, erneuerbare Energien, Wärmewende, energetische Sanierung, Klimaanpassung.",
        "keywords": ["klimaneutral", "klimaschutz", "CO2", "treibhausgas", "erneuerbar", "photovoltaik",
                     "solar", "windkraft", "wärmewende", "fernwärme", "energetische sanierung", "klimaanpassung"],
    },
    "verkehrswende": {
        "label": "Verkehrswende & Radverkehr",
        "description": "Verlagerung des Verkehrs auf Rad, Fuß und ÖPNV; sichere Radwege, Tempo 30, "
                       "Ausbau des Nahverkehrs, weniger Autoverkehr in der Stadt.",
        "keywords": ["radverkehr", "radweg", "fahrrad", "öpnv", "bus", "tempo 30", "fußverkehr",
                     "verkehrswende", "fahrradstraße", "nahverkehr", "schutzstreifen",
                     "parkhaus", "tiefgarage", "stellplatz"],  # incl. car-infra (potential "bremst")
    },
    "wohnungsbau": {
        "label": "Bezahlbarer Wohnungsbau",
        "description": "Schaffung von bezahlbarem und sozialem Wohnraum, Nachverdichtung, "
                       "neue Wohnquartiere, Mietpreisbindung.",
        "keywords": ["wohnungsbau", "wohnraum", "sozialwohnung", "sozialer wohnungsbau", "miete",
                     "bebauungsplan", "wohnquartier", "nachverdichtung", "baulandentwicklung"],
    },
    "bildung_betreuung": {
        "label": "Kita- & Schulausbau",
        "description": "Ausbau von Kinderbetreuung und Schulen: neue Kitas, Krippenplätze, "
                       "Ganztag, Schulsanierung und -neubau.",
        "keywords": ["kita", "kindertagesstätte", "krippe", "kinderbetreuung", "ganztag",
                     "schulneubau", "schulsanierung", "grundschule", "betreuungsplatz"],
    },
    "innenstadt": {
        "label": "Lebendige Innenstadt",
        "description": "Stärkung der Innenstadt: Einzelhandel, Aufenthaltsqualität, gegen Leerstand, "
                       "Fußgängerzone, Märkte und Veranstaltungen.",
        "keywords": ["innenstadt", "fußgängerzone", "einzelhandel", "leerstand", "city",
                     "aufenthaltsqualität", "wochenmarkt", "innenstadtentwicklung"],
    },
    "digitalisierung": {
        "label": "Digitale Verwaltung",
        "description": "Digitalisierung der Stadtverwaltung und Infrastruktur: Online-Dienste, "
                       "Breitband/Glasfaser, IT-Modernisierung, Smart City.",
        "keywords": ["digital", "online-dienst", "breitband", "glasfaser", "smart city",
                     "e-government", "it-", "verwaltungsdigitalisierung"],
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
Regeln: jede vorgelegte id genau einmal mit exakt dieser id; im Zweifel relevant=false.

BESCHLÜSSE:
{items}"""


def _render(decisions: list[dict]) -> str:
    lines = []
    for d in decisions:
        text = d.get("summary") or d.get("beschluss") or ""
        text = " ".join(text.split())[:300]
        lines.append(f'- id {d["id"]}: {(d.get("title") or "").strip()} — {text}')
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
