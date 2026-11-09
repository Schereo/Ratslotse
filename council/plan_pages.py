"""Übersicht und Detailseite „Pläne der Stadt“ — fertig gebaut für Web und App.

Gruppe (laufend, in Arbeit, abgelaufen), Sortierung, Kicker, „letzter
Bericht“ und die Lücken-Sätze entstehen hier und nicht im Frontend: Die App
bekommt dieselben Felder und baut nichts nach (Plan § 4, „Logik ins Backend“).

Was die Seite NICHT tut (§ 2, § 3.4): keine Note, keine Quote über Pläne, kein
„zu langsam“. Wo der Bestand schweigt, sagt sie das — mit Datum.
"""
from __future__ import annotations

from datetime import date as _date

from council import plans as register

#: Kurze Themenfeld-Namen für den Kicker. Die langen stehen in
#: ``council.topics.POLICY_FIELDS``; im Kicker wären sie eine halbe Zeile.
FIELD_SHORT: dict[str, str] = {
    "klima_umwelt": "Klima & Umwelt",
    "verkehr": "Verkehr",
    "bauen_wohnen": "Stadtentwicklung & Wohnen",
    "soziales_gesundheit": "Soziales",
    "bildung": "Bildung",
    "finanzen": "Finanzen",
    "kultur_sport": "Kultur & Sport",
    "wirtschaft": "Wirtschaft",
    "sicherheit_ordnung": "Sicherheit",
    "verwaltung_digital": "Verwaltung & Digitales",
    "migration_integration": "Integration",
    "sonstiges": "Sonstiges",
}

GROUPS: tuple[tuple[str, str], ...] = (
    ("running", "Laufend"),
    ("preparing", "In Arbeit"),
    ("ended", "Abgelaufen oder abgelöst"),
)

STATUS_LABELS = {
    "running": "läuft",
    "preparing": "in Arbeit",
    "superseded": "abgelöst",
    "concluded": "abgeschlossen",
    "expired": "Laufzeit vorbei",
}

#: Rollen, die im Zeitstrahl BERICHTE stehen (der Beschluss als Station dazu).
TIMELINE_ROLES = ("preparation", "adoption", "amendment", "report", "evaluation")
REPORT_ROLES = ("report", "evaluation")

#: So heißen die Blöcke unter BESCHLÜSSE ZUM PLAN (§ 3.2 Nr. 6).
DECISION_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("plan", "Beschließt oder ändert den Plan", ("adoption", "amendment")),
    ("implementation", "Setzt den Plan um", ("implementation",)),
    ("motion", "Antrag oder Anfrage dazu", ("motion",)),
    ("decision", "Weitere Beschlüsse dazu", ("decision",)),
)

#: Ab wie vielen Tagen ohne Bericht die Karte das sagt (§ 3.3a: zwei Jahre).
STALE_DAYS = 730

#: Die Vorlage im Ratsinformationssystem der Stadt.
VORLAGE_URL = "https://buergerinfo.oldenburg.de/vo0050.php?__kvonr={kvonr}"


def vorlage_url(kvonr: int | None) -> str | None:
    return VORLAGE_URL.format(kvonr=kvonr) if kvonr else None


def _month(iso: str | None) -> str | None:
    """``"2022-12-19"`` → ``"12/2022"``, ``"2035"`` → ``"2035"``."""
    if not iso:
        return None
    teile = iso.split("-")
    return teile[0] if len(teile) == 1 else f"{teile[1]}/{teile[0]}"


def _end_date(iso: str) -> str:
    teile = iso.split("-")
    if len(teile) == 1:
        return f"{iso}-12-31"
    if len(teile) == 2:
        return f"{iso}-31"
    return iso


def _start_date(iso: str) -> str:
    """``"2026"`` → ``"2026-01-01"``, ``"2026-06"`` → ``"2026-06-01"``."""
    teile = iso.split("-")
    return "-".join(teile + ["01"] * (3 - len(teile)))


def _stem(number: str | None) -> str | None:
    return register.template_stem(number) if number else None


def status(plan: register.Plan, today: str) -> str:
    if plan.adopted is None:
        return "preparing"
    if plan.successor and register.PLANS[plan.successor].adopted is not None:
        return "superseded"
    if plan.concluded:
        return "concluded"
    if plan.end and _end_date(plan.end) < today:
        return "expired"
    return "running"


def group_of(state: str) -> str:
    return state if state in ("running", "preparing") else "ended"


def _first_date(items: list[dict], number: str | None) -> str | None:
    stem = _stem(number)
    dates = [i["date"] for i in items if stem and _stem(i["template_number"]) == stem]
    return min(dates) if dates else None


def kicker(plan: register.Plan, items: list[dict]) -> str:
    teile = [FIELD_SHORT.get(plan.policy_field, plan.policy_field)]
    if plan.source == "website":
        teile.append(f"veröffentlicht {_month(plan.start)}")
    elif plan.adopted:
        verb = "zur Kenntnis" if plan.adopted.mode == "noted" else "beschlossen"
        teile.append(f"{verb} {_month(plan.adopted.date)}")
    elif plan.commissioned:
        seit = _first_date(items, plan.commissioned)
        teile.append(f"in Arbeit seit {_month(seit)}" if seit else "in Arbeit")
    if plan.end:
        teile.append(f"bis {_month(plan.end)}")
    return " · ".join(teile)


def _days_between(a: str, b: str) -> int:
    return (_date.fromisoformat(b) - _date.fromisoformat(a)).days


def _latest_report(plan: register.Plan, items: list[dict]) -> dict | None:
    """Der jüngste Bericht seit dem Beschluss (bei Plänen in Arbeit: überhaupt)."""
    since = plan.adopted.date if plan.adopted else ""
    reports = [i for i in items if i["role"] in REPORT_ROLES and i["date"] >= since]
    if not reports:
        return None
    r = max(reports, key=lambda i: (i["date"], i["agenda_item_id"]))
    return {"title": r["title"], "date": r["date"], "committee": r["committee"],
            "oral": bool(r["oral"]), "template_number": r["template_number"],
            "decision_id": r["decision_id"]}


def report_note(plan: register.Plan, latest: dict | None, state: str, today: str) -> str | None:
    """Der Satz, wenn der Bestand schweigt — eine Aussage über den Bericht, nicht die Arbeit."""
    if state in ("superseded", "concluded"):
        return None
    if latest is None:
        if plan.adopted is None:
            return "Noch kein Bericht im Rat."
        if plan.adopted.template is None:
            return "Kein Umsetzungsbericht im Ratsinformationssystem (Bestand ab 2018)."
        if _days_between(_start_date(plan.adopted.date), today) < 365:
            return f"Seit dem Beschluss {_month(plan.adopted.date)} noch kein Bericht im Rat."
        return "Kein Umsetzungsbericht im Rat seit dem Beschluss."
    if _days_between(latest["date"], today) > STALE_DAYS:
        return f"Seit {_month(latest['date'])} kein Bericht im Rat."
    return None


def _card(plan: register.Plan, items: list[dict], today: str) -> dict:
    state = status(plan, today)
    latest = _latest_report(plan, items)
    return {
        "key": plan.key,
        "title": plan.title,
        "office": plan.office,
        "kind": plan.kind,
        "kind_label": register.KIND_LABELS[plan.kind],
        "policy_field": plan.policy_field,
        "field_label": FIELD_SHORT.get(plan.policy_field, plan.policy_field),
        "kicker": kicker(plan, items),
        "status": state,
        "status_label": STATUS_LABELS[state],
        "group": group_of(state),
        "adoption_mode": plan.adopted.mode if plan.adopted else None,
        "latest_report": latest,
        "report_note": report_note(plan, latest, state, today),
        "report_count": len({_stem(i["template_number"]) or f"top{i['agenda_item_id']}"
                             for i in items if i["role"] in REPORT_ROLES}),
        "successor": _neighbour(plan.successor),
    }


def _neighbour(key: str | None) -> dict | None:
    if not key:
        return None
    p = register.PLANS[key]
    return {"key": p.key, "title": p.title, "adopted": p.adopted is not None}


def _sorted(cards: list[dict]) -> list[dict]:
    """Nach Themenfeld, darin der jüngste Bericht zuerst (§ 3.1). Stabil sortiert, von hinten."""
    out = sorted(cards, key=lambda c: c["title"])
    out.sort(key=lambda c: (c["latest_report"] or {}).get("date") or "", reverse=True)
    out.sort(key=lambda c: c["field_label"])
    return out


def overview(store, today: str | None = None) -> dict:
    today = today or _date.today().isoformat()
    by_plan: dict[str, list[dict]] = {}
    for item in store.plan_items():
        by_plan.setdefault(item["plan_key"], []).append(item)
    cards = [_card(p, by_plan.get(p.key, []), today) for p in register.PLANS.values()]

    groups = []
    for key, label in GROUPS:
        members = _sorted([c for c in cards if c["group"] == key and c["kind"] != "reference"])
        groups.append({"key": key, "label": label, "plans": members})
    references = _sorted([c for c in cards if c["kind"] == "reference"])
    return {"as_of": today, "groups": groups, "references": references,
            "count": sum(len(g["plans"]) for g in groups)}


def _decision_ref(store, d: register.Decision | None, items: list[dict]) -> dict | None:
    if d is None:
        return None
    found = store.plan_decision_at(d.template, d.date, d.committee) if d.template else None
    kv = store.plan_template_kvonr([d.template]).get(d.template) if d.template else None
    return {
        "date": d.date, "committee": d.committee, "mode": d.mode, "label": d.label,
        "template_number": d.template, "kvonr": kv, "url": vorlage_url(kv),
        "decision_id": found["id"] if found else None,
        "outcome": found["outcome"] if found else None,
        "vote": found["vote"] if found else None,
    }


def _template_ref(store, number: str | None, items: list[dict]) -> dict | None:
    if not number:
        return None
    kv = store.plan_template_kvonr([number]).get(number)
    return {"template_number": number,
            "title": store.plan_template_titles([number]).get(number),
            "kvonr": kv, "url": vorlage_url(kv),
            "date": _first_date(items, number)}


def _grouped(items: list[dict]) -> list[list[dict]]:
    """Ein Eintrag je Vorlage (alle Beratungen zusammen), mündliche einzeln."""
    groups: dict[str, list[dict]] = {}
    for i in items:
        k = _stem(i["template_number"]) or f"top{i['agenda_item_id']}"
        groups.setdefault(k, []).append(i)
    return sorted(groups.values(), key=lambda g: (g[0]["date"], g[0]["agenda_item_id"]))


def timeline(items: list[dict]) -> dict:
    stations = []
    for g in _grouped([i for i in items if i["role"] in TIMELINE_ROLES]):
        last = g[-1]
        stations.append({
            "date": g[0]["date"],
            "date_end": last["date"] if last["date"] != g[0]["date"] else None,
            "kind": last["role"],
            "title": last["title"],
            "template_number": last["template_number"],
            "oral": bool(last["oral"]),
            "committees": sorted({i["committee"] for i in g if i["committee"]}),
            "decision_id": next((i["decision_id"] for i in reversed(g) if i["decision_id"]), None),
            "members": [{"date": i["date"], "committee": i["committee"], "decision_id": i["decision_id"]}
                        for i in g],
        })
    span = f"{stations[0]['date'][:4]}–{stations[-1]['date'][:4]}" if stations else ""
    return {"span": span, "count": len(stations), "stations": stations}


def _entries(items: list[dict]) -> list[dict]:
    out = []
    for g in _grouped(items):
        last = g[-1]
        with_decision = [i for i in g if i["decision_id"]]
        best = with_decision[-1] if with_decision else last
        out.append({"title": best["title"], "date": best["date"], "committee": best["committee"],
                    "decision_id": best["decision_id"], "outcome": best["outcome"],
                    "template_number": best["template_number"], "deliberations": len(g)})
    out.sort(key=lambda e: e["date"], reverse=True)
    return out


def detail(store, key: str, today: str | None = None) -> dict | None:
    plan = register.PLANS.get(key)
    if plan is None:
        return None
    today = today or _date.today().isoformat()
    items = store.plan_items(key)
    card = _card(plan, items, today)
    groups = [{"key": k, "label": label, "entries": _entries([i for i in items if i["role"] in roles])}
              for k, label, roles in DECISION_GROUPS]
    mentions = [{"title": m["title"], "date": m["session_date"], "committee": m["committee"],
                 "decision_id": m["id"], "outcome": m["outcome"], "template_number": m["template_number"],
                 "deliberations": 1} for m in store.plan_mentions(key)]
    groups.append({"key": "mentions", "label": "Erwähnt den Plan über seine Vorlagennummer",
                   "entries": mentions})
    return {
        **card,
        "note": plan.note,
        "owner": plan.owner,
        "source": plan.source,
        "start": plan.start,
        "end": plan.end,
        "start_label": _month(plan.start),
        "end_label": _month(plan.end),
        "horizon_note": plan.horizon_note,
        "review_due": plan.review_due,
        "review_label": _month(plan.review_due),
        "adoption": _decision_ref(store, plan.adopted, items),
        "decisions": [r for d in plan.decisions if (r := _decision_ref(store, d, items))],
        "commissioned": _template_ref(store, plan.commissioned, items),
        "concluded": _template_ref(store, plan.concluded, items),
        "predecessor": _neighbour(plan.predecessor),
        "timeline": timeline(items),
        "decision_groups": [g for g in groups if g["entries"]],
        "goal": plan.goal,
    }
