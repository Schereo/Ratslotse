"""Classify council decisions into policy fields (Themenfelder).

One LLM pass over a *batch* of decisions returns, per decision, a single policy
field from a closed taxonomy, a few free-form tags and a one-line summary. This is
owner-agnostic (like ``protocols.py``) and forms the foundation for topic filtering,
party-by-topic analysis and goal tracking.
"""
from __future__ import annotations

import json
import logging
import os

from nwz import llm

MODEL = os.environ.get("COUNCIL_TOPIC_MODEL", "deepseek/deepseek-v4-pro")

logger = logging.getLogger("council.topics")

# Closed taxonomy: key -> (German label, description fed to the LLM).
POLICY_FIELDS: dict[str, tuple[str, str]] = {
    "verkehr": ("Verkehr & Mobilität", "Straßen, Radverkehr, ÖPNV, Parken, Brücken, Verkehrsplanung"),
    "klima_umwelt": ("Klima, Umwelt & Energie", "Klimaschutz, Energie, Grünflächen, Natur-/Gewässerschutz, Abfall"),
    "bauen_wohnen": ("Bauen, Stadtentwicklung & Wohnen", "Bebauungspläne, Wohnungsbau, Quartiere, Flächennutzung, Sanierung"),
    "soziales_gesundheit": ("Soziales & Gesundheit", "Pflege, Senioren, Inklusion, Gesundheit, Wohlfahrt, Teilhabe"),
    "bildung": ("Bildung, Kita & Schule", "Schulen, Kitas, Kinderbetreuung, Volkshochschule, Bildungsangebote"),
    "finanzen": ("Finanzen & Haushalt", "Haushalt, Steuern, Gebühren, Förderungen, städtische Beteiligungen, Vergaben"),
    "kultur_sport": ("Kultur, Sport & Freizeit", "Kultur, Museen, Sport, Vereine, Spielplätze, Veranstaltungen, Tourismus"),
    "wirtschaft": ("Wirtschaft & Arbeit", "Wirtschaftsförderung, Gewerbe, Einzelhandel, Märkte, Arbeitsmarkt"),
    "sicherheit_ordnung": ("Sicherheit & Ordnung", "Feuerwehr, Ordnungsamt, Brand-/Katastrophenschutz, öffentliche Sicherheit"),
    "verwaltung_digital": ("Verwaltung, Digitales & Organisation", "Interne Organisation, Personal, IT/Digitalisierung, Satzungen, Gremien, Wahlen"),
    "migration_integration": ("Migration & Integration", "Geflüchtete, Unterbringung, Integration, Migrationsberatung"),
    "sonstiges": ("Sonstiges", "Passt in keines der übrigen Felder"),
}

FIELD_KEYS = list(POLICY_FIELDS)

_PROMPT = """Du ordnest Beschlüsse/Berichte eines Stadtrats (Oldenburg) in Themenfelder ein.

Themenfelder (Schlüssel: Beschreibung):
{fields}

Für JEDEN Eintrag liefere:
- "field": GENAU EIN Schlüssel aus der Liste (der am besten passende)
- "tags": 1-3 feinere Schlagworte (frei, deutsch, z.B. "Radverkehr", "Kita-Ausbau"); [] wenn unklar
- "summary": EIN knapper, neutraler Satz (max. 140 Zeichen), was beschlossen/berichtet wurde

Antworte mit NUR JSON in dieser Form:
{{"results": [{{"id": <id>, "field": "<schlüssel>", "tags": ["..."], "summary": "..."}}]}}

Regeln:
- Gib für JEDE vorgelegte id genau ein Ergebnis mit exakt derselben id zurück.
- "field" MUSS einer der Schlüssel sein; im Zweifel "sonstiges".
- Erfinde nichts; fasse nur den vorgelegten Text zusammen.
- Berufung, Besetzung, Umbesetzung oder Benennung von Mitgliedern in Ausschüssen,
  Gremien, Beiräten, Aufsichtsräten oder Kommissionen → IMMER "verwaltung_digital"
  (Gremien/Wahlen), unabhängig vom Fachthema des Gremiums (eine Schulausschuss-
  Besetzung ist "verwaltung_digital", nicht "bildung"; ein Sportausschuss-Sitz
  ebenso, nicht "kultur_sport").
- Bei Förder-, Zuwendungs- oder Bewilligungsbeschlüssen richtet sich "field" nach dem
  geförderten SACHBEREICH (Jugendkulturverein → "kultur_sport", Feuerwehr →
  "sicherheit_ordnung"), NICHT nach "finanzen". "finanzen" nur, wenn der Beschluss
  selbst der Haushalt, ein Wirtschaftsplan, eine städtische Beteiligung oder eine
  Steuer/Abgabe ist.

EINTRÄGE:
{items}"""


def _strip_fences(content: str) -> str:
    """Strip a ```json … ``` markdown fence the model sometimes adds."""
    c = content.strip()
    if c.startswith("```"):
        c = c.strip("`").strip()
        if c.lower().startswith("json"):
            c = c[4:].strip()
    return c


def _render_items(decisions: list[dict]) -> str:
    lines = []
    for d in decisions:
        title = (d.get("title") or "").strip()
        beschluss = " ".join((d.get("beschluss") or "").split())
        if len(beschluss) > 400:
            beschluss = beschluss[:400] + "…"
        committee = d.get("committee") or ""
        lines.append(f'- id {d["id"]}: [{committee}] {title}\n  Beschluss: {beschluss}')
    return "\n".join(lines)


def classify_batch(decisions: list[dict], model: str = MODEL):
    """Classify a batch of decisions in one LLM call.

    Returns ``(results_by_id, usage)`` where ``results_by_id`` maps decision id ->
    ``{"field", "tags", "summary"}``. Retries once on an empty/unparseable reply;
    raises if it still yields nothing usable so the caller can mark/skip the batch.
    """
    fields = "\n".join(f"- {k}: {v[1]}" for k, v in POLICY_FIELDS.items())
    prompt = _PROMPT.format(fields=fields, items=_render_items(decisions))
    extra: dict = {}
    if "deepseek" in model:
        extra = {"extra_body": {"reasoning": {"enabled": False}}}
    messages = [{"role": "user", "content": prompt}]
    valid_ids = {d["id"] for d in decisions}
    last_err: Exception = ValueError("no response")
    for _ in range(2):
        resp = llm.chat_complete(
            model=model, temperature=0, response_format={"type": "json_object"},
            max_tokens=4000, messages=messages, **extra,
        )
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
            if rid not in valid_ids:
                continue
            field = r.get("field")
            if field not in POLICY_FIELDS:
                field = "sonstiges"
            tags = r.get("tags") or []
            if not isinstance(tags, list):
                tags = []
            tags = [str(t).strip() for t in tags if str(t).strip()][:3]
            summary = (r.get("summary") or "").strip()[:200] or None
            out[rid] = {"field": field, "tags": tags, "summary": summary}
        if out:
            return out, resp.usage
        last_err = ValueError("no valid results")
    raise last_err
