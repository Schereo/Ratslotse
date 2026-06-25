"""Extract named entities (projects, places, organizations) from decisions via LLM.

One pass over a *batch* of decisions returns, per decision, the proper names of
recurring projects, places/structures and organizations. After a slug-based grouping
these become the basis for entity ("Themen-") pages that aggregate everything about
e.g. "Fliegerhorst", "Klinikum Oldenburg" or "Huntebrücke".
"""
from __future__ import annotations

import json
import logging
import os
import re

from nwz import llm

MODEL = os.environ.get("COUNCIL_ENTITY_MODEL", "deepseek/deepseek-v4-pro")

logger = logging.getLogger("council.entities")

KINDS = ("projekt", "ort", "organisation")

_PROMPT = """Du extrahierst aus Stadtrats-Beschlüssen die EIGENNAMEN, die als Schlagwort für eine Themen-Seite taugen — wiederkehrende Projekte, Orte/Bauwerke/Quartiere und Organisationen, mit denen sich der Rat befasst.

Pro Eintrag:
- "name": kürzeste kanonische Form (»Fliegerhorst«, nicht »ehemaliger Fliegerhorst«; »Klinikum Oldenburg«, nicht »Klinikum Oldenburg AöR«; »Weser-Ems-Halle«; »Nadorster Straße«)
- "kind": "projekt" | "ort" | "organisation"

Regeln:
- Nur konkrete Eigennamen, die das Thema des Beschlusses sind. KEINE generischen Begriffe (Stadt, Rat, Verwaltung, Haushalt, Beschluss, Ausschuss, Bericht, Antrag, Satzung).
- Lasse Rechtsformen (GmbH, AöR, e.V., KG, Beteiligungs-GmbH) und Ortszusätze (Oldenburg, Stadt) weg, wenn der Kern eindeutig bleibt: »Weser-Ems-Halle« (nicht »Weser-Ems Halle Oldenburg Beteiligungs-GmbH«), »Klinikum Oldenburg«.
- KEINE Neben-Organisationen wie Wirtschaftsprüfer, Treuhänder oder Gutachter — nur der eigentliche Gegenstand.
- KEINE Partei-/Fraktionsnamen und keine Personennamen.
- Höchstens 4 je Beschluss; leere Liste, wenn keiner passt.
- Gib für JEDE vorgelegte id genau ein Ergebnis mit exakt dieser id zurück.

Antworte mit NUR JSON: {{"results": [{{"id": <id>, "entities": [{{"name": "...", "kind": "..."}}]}}]}}

BESCHLÜSSE:
{items}"""


def _render(decisions: list[dict]) -> str:
    lines = []
    for d in decisions:
        title = (d.get("title") or "").strip()
        beschluss = " ".join((d.get("beschluss") or "").split())[:300]
        lines.append(f'- id {d["id"]}: {title} — {beschluss}')
    return "\n".join(lines)


def _strip_fences(content: str) -> str:
    c = content.strip()
    if c.startswith("```"):
        c = c.strip("`").strip()
        if c.lower().startswith("json"):
            c = c[4:].strip()
    return c


# Legal-form / city tokens dropped from the grouping key so "Weser-Ems-Halle … GmbH"
# and "Weser-Ems-Halle" collapse to one entity.
_SLUG_DROP = {"gmbh", "aoer", "ev", "kg", "mbh", "co", "oldenburg", "oldb"}


def slug(name: str) -> str:
    """Grouping/URL key: lowercase, umlauts folded, legal-form/city noise removed."""
    s = name.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    tokens = [t for t in re.split(r"[^a-z0-9]+", s) if t and t not in _SLUG_DROP]
    return "-".join(tokens)


def extract_batch(decisions: list[dict], model: str = MODEL):
    """One LLM call over a batch → ``(results_by_id, usage)`` with
    id -> ``[{"name", "kind"}]``. Retries once; raises if nothing usable."""
    prompt = _PROMPT.format(items=_render(decisions))
    extra: dict = {"extra_body": {"reasoning": {"enabled": False}}} if "deepseek" in model else {}
    valid_ids = {d["id"] for d in decisions}
    last_err: Exception = ValueError("no response")
    for _ in range(2):
        resp = llm.chat_complete(
            model=model, temperature=0, response_format={"type": "json_object"},
            max_tokens=4000, messages=[{"role": "user", "content": prompt}], **extra,
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
        out: dict[int, list] = {}
        for r in data.get("results", []):
            try:
                rid = int(r["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if rid not in valid_ids:
                continue
            ents = []
            for e in (r.get("entities") or [])[:4]:
                name = (e.get("name") or "").strip()
                kind = e.get("kind") if e.get("kind") in KINDS else "projekt"
                if len(name) >= 3 and slug(name):
                    ents.append({"name": name, "kind": kind})
            out[rid] = ents
        if out:
            return out, resp.usage
        last_err = ValueError("no valid results")
    raise last_err
