"""Was im Bestand zu einem Plan gehört — ohne Modell (Plan „Pläne der Stadt“, Phase 1).

Zwei Wege, beide sicher genug, um ohne Prüfung angezeigt zu werden
(docs/plan-ziele-plaene.md § 1.4):

1. **Tagesordnungspunkte über den Titel** (``council_plan_items``): Jeder Punkt,
   dessen Titel ein Berichtsmuster des Plans trifft oder dessen Vorlage das
   Register nennt, bekommt eine Rolle — Beschluss des Plans, Fortschreibung,
   Auswertung, Bericht, Vorbereitung, Umsetzung, Antrag, sonstiger Beschluss.
   Mündliche Berichte ohne Vorlage zählen mit; sie haben keinen Text, aber
   Termin und Gremium sind selbst eine Aussage.
2. **Verweis über die Vorlagennummer** (``council_plan_links``, ``mentions``):
   Eine andere Vorlage nennt die Nummer des Plans in ihrem Text. Das ist eine
   Erwähnung, keine Umsetzung, und steht auf der Seite hinter „Weitere“.

Ein Verweis über den **Namen** („Klimaschutzplan“ in 103 Vorlagen) ist nur ein
Kandidat und kommt erst mit dem Modellurteil in Phase 4.

**Ketten teilen sich Muster.** Aktionsplan Gewalt 2020 und 2026, die drei
Gleichstellungspläne: Ein Bericht gehört dem Glied, das zu seinem Datum galt —
dem letzten, das vorher beschlossen (oder begonnen) war. Wo die Vorlage selbst
im Register steht, entscheidet sie, nicht das Datum: Die Evaluation von 2026
ist für den alten Plan die Auswertung und für den neuen der Beschluss.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from council import plans as register

#: Das RIS hängt das Ergebnis an den Titel an („… - Bericht Beschluss: zur
#: Kenntnis genommen Abstimmung: …“). Für die Einordnung zählt nur der Titel.
_ERGEBNIS_ANHANG = re.compile(r"\s+(Beschluss|Abstimmung):.*$", re.S)
#: Antrag oder Anfrage einer Fraktion, Gruppe oder eines beratenden Mitglieds:
#: „(Fraktion … vom 28.02.2022)“, „; Bündnis 90/Die Grünen, 27.08.2020“.
_ANTRAG = re.compile(r"vom \d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}\s*\)|[,;]\s*\d{1,2}\.\d{1,2}\.\d{4}\s*$")
_BERICHT = re.compile(
    r"Bericht|Sachstand|Umsetzungsstand|Zwischenstand|Aktueller Stand|Stand der|Monitoring|"
    r"Aktivitäten|Evaluation|Vorstellung|Ergebnis|Informationsveranstaltung", re.I)
_MUENDLICH = re.compile(r"mündl|mdl\.", re.I)
_TOP_PRAEFIX = re.compile(r"^[ÖN]\s+", re.I)
_NUMMER = re.compile(r"(?<![\d/])(\d{2}/\d{4})(?:/\d+)?(?!\d)")

ROLES = ("adoption", "amendment", "evaluation", "report", "preparation",
         "implementation", "motion", "decision")


@dataclass(frozen=True)
class AgendaRow:
    """Ein Tagesordnungspunkt samt Sitzung, Vorlagenart und Beschluss (falls protokolliert)."""

    agenda_item_id: int
    ksinr: int
    item_number: str | None
    date: str
    committee: str | None
    title: str
    template_number: str | None
    kvonr: int | None
    template_kind: str | None
    decision_id: int | None
    outcome: str | None


def clean_title(title: str) -> str:
    return _ERGEBNIS_ANHANG.sub("", title or "").strip()


def decision_item_number(agenda_number: str | None) -> str:
    """„Ö 11.2“ → „11.2“: So steht die Nummer in ``council_decisions``."""
    return _TOP_PRAEFIX.sub("", (agenda_number or "").strip()).strip()


def _stem(number: str | None) -> str | None:
    return register.template_stem(number) if number else None


def _anchor(plan: register.Plan, first_seen: dict[str, str]) -> str | None:
    """Ab wann ein Kettenglied für neue Berichte zuständig ist."""
    if plan.adopted:
        return plan.adopted.date
    if plan.commissioned:
        return first_seen.get(register.template_stem(plan.commissioned))
    return plan.start


def _chain(plan: register.Plan) -> tuple[str, ...]:
    """Alle Glieder der Kette, ältestes zuerst."""
    first = plan
    while first.predecessor:
        first = register.PLANS[first.predecessor]
    out = [first.key]
    while register.PLANS[out[-1]].successor:
        out.append(register.PLANS[out[-1]].successor)  # type: ignore[arg-type]
    return tuple(out)


def classify(plan: register.Plan, row: AgendaRow) -> str:
    """Die Rolle eines Tagesordnungspunkts für einen Plan, zu dem er gehört."""
    title = clean_title(row.title)
    stem = _stem(row.template_number)
    if stem and plan.adopted and plan.adopted.template and stem == register.template_stem(plan.adopted.template):
        return "adoption"
    if stem and stem in {register.template_stem(d.template) for d in plan.decisions if d.template}:
        return "amendment"
    if stem and plan.concluded and stem == register.template_stem(plan.concluded):
        return "evaluation"
    is_report = bool(_BERICHT.search(title)) or row.template_number is None
    administration_report = (row.template_kind or "").startswith("Berichtsvorlage") and bool(_BERICHT.search(title))
    if _ANTRAG.search(title) and not administration_report:
        return "motion"
    if any(re.search(p, title, re.I) for p in plan.implementation_patterns):
        return "implementation"
    if plan.adopted and row.date < plan.adopted.date:
        return "preparation"
    return "report" if is_report else "decision"


def is_oral(row: AgendaRow) -> bool:
    return row.template_number is None or bool(_MUENDLICH.search(row.title))


def build_items(rows: Iterable[AgendaRow],
                plans: dict[str, register.Plan] | None = None) -> list[dict]:
    """Ordnet Tagesordnungspunkte ihren Plänen zu. Rein, ohne Datenbank."""
    plans = plans if plans is not None else register.PLANS
    rows = list(rows)
    first_seen: dict[str, str] = {}
    for r in rows:
        stem = _stem(r.template_number)
        if stem and (stem not in first_seen or r.date < first_seen[stem]):
            first_seen[stem] = r.date

    own: dict[str, set[str]] = {
        key: {register.template_stem(t) for t in register.all_templates(p)} for key, p in plans.items()}
    out: list[dict] = []
    for row in rows:
        stem = _stem(row.template_number)
        by_template = {k for k, stems in own.items() if stem and stem in stems}
        by_title = {k for k, p in plans.items() if k not in by_template and register.matches_title(p, row.title)}
        # Glieder einer Kette, die dasselbe Muster teilen: nur das zuständige.
        chosen = set(by_template)
        for chain in {_chain(plans[k]) for k in by_title}:
            if any(k in by_template for k in chain):
                continue  # die Vorlage hat ihr Glied schon bestimmt
            members = [k for k in chain if k in by_title]
            zustaendig = members[0]
            for k in members:
                a = _anchor(plans[k], first_seen)
                if a and a <= row.date:
                    zustaendig = k
            chosen.add(zustaendig)
        for key in sorted(chosen):
            role = classify(plans[key], row)
            out.append({
                "plan_key": key, "agenda_item_id": row.agenda_item_id, "ksinr": row.ksinr,
                "item_number": row.item_number, "date": row.date, "committee": row.committee,
                "title": clean_title(row.title), "template_number": row.template_number,
                "kvonr": row.kvonr, "role": role,
                "oral": int(role in ("report", "preparation") and is_oral(row)),
                "decision_id": row.decision_id, "outcome": row.outcome,
            })
    return out


def cited_numbers(text: str | None) -> set[str]:
    """Vorlagennummern (ohne Fassung), die ein Text nennt."""
    return set(_NUMMER.findall(text or ""))


def build_mentions(templates: Iterable[tuple[str, str | None]],
                   decisions_by_stem: dict[str, list[int]],
                   items: list[dict],
                   plans: dict[str, register.Plan] | None = None) -> list[dict]:
    """Beschlüsse zu Vorlagen, die eine Plannummer im Text nennen.

    ``templates``: (Vorlagennummer, Text). Was schon als Tagesordnungspunkt
    zum Plan gehört, kommt hier nicht noch einmal vor.
    """
    plans = plans if plans is not None else register.PLANS
    own = {key: {register.template_stem(t) for t in register.all_templates(p)} for key, p in plans.items()}
    known = {(i["plan_key"], _stem(i["template_number"])) for i in items if i["template_number"]}
    out: dict[tuple[str, int], dict] = {}
    for number, text in templates:
        stem = register.template_stem(number)
        cited = cited_numbers(text)
        if not cited:
            continue
        for key, stems in own.items():
            if stem in stems or (key, stem) in known or not (cited & stems):
                continue
            for decision_id in decisions_by_stem.get(stem, []):
                out[(key, decision_id)] = {
                    "plan_key": key, "decision_id": decision_id, "measure_code": "",
                    "relation": "mentions", "method": "number", "confidence": 1.0}
    return list(out.values())


def build(store) -> dict:
    """Baut beide Tabellen neu. Für den Cron (``scripts/check_protocols.py``)."""
    rows = [AgendaRow(**r) for r in store.plan_tracking_rows()]
    items = build_items(rows)
    links = build_mentions(store.plan_citing_templates(), store.plan_decisions_by_stem(), items)
    store.replace_plan_tracking(items, links)
    per_plan = {key: sum(1 for i in items if i["plan_key"] == key) for key in register.PLANS}
    return {
        "plan_items": len(items),
        "plan_reports": sum(1 for i in items if i["role"] in ("report", "evaluation")),
        "plan_mentions": len(links),
        "plans_without_items": sum(1 for n in per_plan.values() if n == 0),
    }
