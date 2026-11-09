"""Übersicht und Detailseite „Pläne der Stadt“ — fertig gebaut für Web und App.

Gruppe (laufend, in Arbeit, abgelaufen), Sortierung, Kicker, „letzter
Bericht“ und die Lücken-Sätze entstehen hier und nicht im Frontend: Die App
bekommt dieselben Felder und baut nichts nach (Plan § 4, „Logik ins Backend“).

Was die Seite NICHT tut (§ 2, § 3.4): keine Note, keine Quote über Pläne, kein
„zu langsam“. Wo der Bestand schweigt, sagt sie das — mit Datum.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date as _date

from council import plan_state
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

#: Der Satz neben „kein Bericht“ (§ 3.3a): Die Lücke sagt etwas über die
#: Berichte, nichts über die Arbeit.
REPORT_CAVEAT = ("Das ist eine Aussage über die Berichte, nicht über die Arbeit: "
                 "Ob umgesetzt wurde, wissen wir nicht.")

#: Die gemeinsame Zeitachse der Übersicht beginnt, wo der Bestand beginnt
#: (Sitzungen ab 01/2018), und reicht zehn Jahre nach vorn.
ARCHIVE_START = "2018-01-01"
AXIS_YEARS_AHEAD = 10
#: So viele Jahre hinter heute läuft ein Band ohne Enddatum blass aus.
OPEN_END_YEARS = 3

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
        # Der echte Monatsletzte — „2029-09-31“ gibt es nicht, und das Zeitband rechnet mit dem Tag.
        return f"{iso}-{monthrange(int(teile[0]), int(teile[1]))[1]:02d}"
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


def timing(plan: register.Plan, items: list[dict]) -> str:
    """Der Kicker ohne Themenfeld: „beschlossen 12/2022 · bis 2035“."""
    return " · ".join(_kicker_parts(plan, items)[1:])


def kicker(plan: register.Plan, items: list[dict]) -> str:
    return " · ".join(_kicker_parts(plan, items))


def _kicker_parts(plan: register.Plan, items: list[dict]) -> list[str]:
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
    return teile


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


def _silence_is_news(plan: register.Plan, today: str) -> bool:
    """Braucht der Lücken-Satz die Einordnung? Nicht bei Plänen, die jünger als ein Jahr sind."""
    if plan.adopted is None:
        return False
    return _days_between(_start_date(plan.adopted.date), today) >= 365


# ── Zeitband ──────────────────────────────────────────────────────────────
#
# Ein Plan ist eine Strecke in der Zeit: vom Beschluss bis zum Laufzeitende,
# dazwischen die Berichte. Die Übersicht legt alle Pläne auf EINE Achse
# (Bestand ab 2018 bis zehn Jahre nach vorn), die Detailseite jeden auf seine
# eigene. Gerechnet wird hier, gezeichnet im Frontend: Lagen sind Anteile der
# Achse von 0 bis 1.
#
# Das Band ist KEIN Fortschrittsbalken (§ 3.4): Es zeigt, wann ein Plan gilt
# und wann berichtet wurde — nicht, wie viel erledigt ist.

def _mid_date(iso: str) -> str:
    """Eine Angabe ohne Tag in die Mitte ihres Zeitraums: ``"2027"`` → Juli, ``"2031-06"`` → der 15."""
    teile = iso.split("-")
    if len(teile) == 1:
        return f"{iso}-07-01"
    if len(teile) == 2:
        return f"{iso}-15"
    return iso


def _pos(iso: str, start: str, end: str) -> float:
    """Lage eines Tages auf der Achse ``start``…``end`` (ungekappt, vier Stellen)."""
    a, b = _date.fromisoformat(start).toordinal(), _date.fromisoformat(end).toordinal()
    return round((_date.fromisoformat(iso).toordinal() - a) / (b - a), 4)


def _clip(x: float) -> float:
    return min(1.0, max(0.0, x))


def overview_axis(today: str) -> tuple[str, str]:
    return ARCHIVE_START, f"{int(today[:4]) + AXIS_YEARS_AHEAD}-12-31"


def _ticks(start: str, end: str) -> list[dict]:
    """Jahresmarken: jedes Jahr, ab zehn Jahren jedes zweite, ab zwanzig jedes fünfte."""
    first, last = int(start[:4]), int(end[:4])
    years = last - first + 1
    step = 1 if years <= 9 else 2 if years <= 19 else 5
    return [{"label": str(y), "x": _pos(f"{y}-01-01", start, end)}
            for y in range(first, last + 1) if y % step == 0 or (step == 1)]


def _band(plan: register.Plan, items: list[dict], state: str, today: str) -> tuple[str | None, str | None, bool]:
    """Beginn und Ende des Bandes als Tage, dazu: Ist das Ende offen?

    In Arbeit: vom Beginn der Arbeit bis heute. Ohne Enddatum: bis heute, das
    Band läuft dahinter blass aus. Abgelöst ohne Enddatum: bis der Nachfolger
    beschlossen wurde.
    """
    if plan.adopted is None:
        begin = _first_date(items, plan.commissioned) or min((i["date"] for i in items), default=None)
        return begin, (today if begin else None), False
    begin = _start_date(plan.start or plan.adopted.date)
    if plan.end:
        return begin, _end_date(plan.end), False
    successor = register.PLANS[plan.successor].adopted if plan.successor else None
    if state == "superseded" and successor:
        return begin, _start_date(successor.date), False
    if state == "concluded":
        end = _first_date(items, plan.concluded) or max((i["date"] for i in items), default=None)
        return begin, end or begin, False
    return begin, today, True


def _mark_date(station: dict) -> str:
    """Ein Beschluss liegt am Tag des Beschlusses (der letzten Beratung), ein Bericht an seinem ersten."""
    if station["kind"] in ("adoption", "amendment", "evaluation"):
        return station["date_end"] or station["date"]
    return station["date"]


def lane(plan: register.Plan, items: list[dict], state: str, today: str) -> dict:
    """Das Zeitband eines Plans auf der gemeinsamen Achse der Übersicht."""
    start, end = overview_axis(today)
    begin, until, open_end = _band(plan, items, state, today)
    band = None
    if begin and until:
        x0, x1 = _pos(begin, start, end), _pos(until, start, end)
        if x1 > 0 and x0 < 1:
            band = {"x0": _clip(x0), "x1": _clip(x1), "open_start": x0 < 0, "beyond": x1 > 1,
                    "open_end": open_end}
    marks = []
    for s in timeline(items)["stations"]:
        # Die Vorgeschichte (Beratungen vor dem Beschluss) steht auf der Detailseite;
        # hier zeigt das Band, was SEIT dem Beschluss berichtet wurde.
        if s["kind"] == "preparation":
            continue
        x = _pos(_mark_date(s), start, end)
        if 0 <= x <= 1:
            marks.append({"x": x, "date": _mark_date(s), "kind": s["kind"], "oral": s["oral"]})
    tail = None
    if plan.predecessor and begin:
        before = register.PLANS[plan.predecessor]
        if before.adopted:
            t0 = _pos(_start_date(before.start or before.adopted.date), start, end)
            t1 = _pos(_end_date(before.end) if before.end else begin, start, end)
            if t1 > 0 and t1 > t0:
                tail = {"x0": _clip(t0), "x1": _clip(t1)}
    review = _pos(_mid_date(plan.review_due), start, end) if plan.review_due else None
    return {
        "style": "preparing" if plan.adopted is None else plan.adopted.mode,
        "band": band,
        "marks": marks,
        "predecessor": tail,
        "review": review if review is not None and 0 <= review <= 1 else None,
    }


def _months_between(a: str, b: str) -> int:
    d0, d1 = _date.fromisoformat(a), _date.fromisoformat(b)
    months = (d1.year - d0.year) * 12 + (d1.month - d0.month) - (1 if d1.day < d0.day else 0)
    return max(months, 0)


def duration(months: int) -> str:
    """``46`` → ``"3 Jahre, 10 Monate"``; ab fünf Jahren ohne Monate."""
    years, rest = divmod(months, 12)
    months_text = "1 Monat" if rest == 1 else f"{rest} Monate"
    if years == 0:
        return months_text if rest else "weniger als ein Monat"
    years_text = "1 Jahr" if years == 1 else f"{years} Jahre"
    return years_text if rest == 0 or years >= 5 else f"{years_text}, {months_text}"


def since(plan: register.Plan, items: list[dict], state: str, today: str) -> dict | None:
    """Wie lange der Plan schon gilt (oder in Arbeit ist) — nur für Pläne, die noch laufen."""
    if state == "preparing":
        begin, _, _ = _band(plan, items, state, today)
        return {"label": "In Arbeit seit", "value": duration(_months_between(begin, today))} if begin else None
    if state != "running" or plan.adopted is None or len(plan.adopted.date) < 10:
        return None
    label = "Seit der Kenntnisnahme" if plan.adopted.mode == "noted" else "Seit dem Beschluss"
    return {"label": label, "value": duration(_months_between(plan.adopted.date, today))}


def remaining(plan: register.Plan, state: str, today: str) -> dict | None:
    if state != "running" or not plan.end:
        return None
    return {"label": "Laufzeit noch", "value": duration(_months_between(today, _end_date(plan.end)))}


def runway(plan: register.Plan, items: list[dict], state: str, today: str, stations: list[dict]) -> dict | None:
    """Das Zeitband der Detailseite: eine eigene Achse je Plan, jede Station eine Marke."""
    begin, until, open_end = _band(plan, items, state, today)
    days = [d for s in stations for d in (s["date"], s["date_end"]) if d]
    if not begin and not days:
        return None
    alive = state in ("running", "preparing")
    highs = days + [d for d in (until, today if alive else None,
                                _mid_date(plan.review_due) if plan.review_due else None) if d]
    start = f"{min(days + ([begin] if begin else []))[:4]}-01-01"
    last = max(int(max(highs)[:4]), int(today[:4]) + OPEN_END_YEARS if open_end else 0)
    end = f"{last}-12-31"
    band = None
    if begin and until:
        band = {"x0": _clip(_pos(begin, start, end)), "x1": _clip(_pos(until, start, end)),
                "open_start": False, "beyond": False, "open_end": open_end}
    return {
        "start": start,
        "end": end,
        "ticks": _ticks(start, end),
        "today": _pos(today, start, end) if start <= today <= end else None,
        "style": "preparing" if plan.adopted is None else plan.adopted.mode,
        "band": band,
        "marks": [{"x": _pos(_mark_date(s), start, end), "date": _mark_date(s), "kind": s["kind"],
                   "oral": s["oral"], "station": i} for i, s in enumerate(stations)],
        "review": ({"x": _pos(_mid_date(plan.review_due), start, end), "label": _month(plan.review_due)}
                   if plan.review_due else None),
        #: Vor 2018 kennt das Ratsinformationssystem keine Sitzungen: Dort
        #: stehen keine Marken, weil es keine Daten gibt — nicht, weil nichts war.
        "archive_from": _pos(ARCHIVE_START, start, end) if start < ARCHIVE_START else None,
    }


def year_log(plan: register.Plan, items: list[dict], state: str, today: str, stations: list[dict]) -> list[dict]:
    """Der Zeitstrahl nach Jahren, das jüngste zuerst — samt der Jahre, in denen nichts zu finden war.

    Eine Lücke ist eine Aussage über den Bestand („keinen gefunden“), nie über
    die Arbeit. Sie zählt erst nach dem Jahr des Beschlusses und frühestens ab
    2018; aufeinanderfolgende Jahre stehen als ein Eintrag.
    """
    by_year: dict[int, list[int]] = {}
    for i, s in enumerate(stations):
        by_year.setdefault(int(s["date"][:4]), []).append(i)
    begin, until, _ = _band(plan, items, state, today)
    this_year = int(today[:4])
    gaps: list[int] = []
    if begin and plan.kind != "reference":
        last = this_year if state in ("running", "preparing") else min(this_year, int((until or today)[:4]))
        first = int(begin[:4]) + 1 if begin >= ARCHIVE_START else int(ARCHIVE_START[:4])
        gaps = [y for y in range(first, last + 1) if y not in by_year]
    out: list[dict] = []
    years = sorted(set(by_year) | set(gaps), reverse=True)
    for y in years:
        if y in by_year:
            out.append({"kind": "year", "year": y, "year_to": y, "stations": sorted(by_year[y], reverse=True),
                        "text": None})
        elif out and out[-1]["kind"] == "gap" and out[-1]["year"] == y + 1:
            out[-1]["year"] = y
        else:
            out.append({"kind": "gap", "year": y, "year_to": y, "stations": [], "text": None})
    for e in out:
        if e["kind"] == "gap":
            only_now = e["year"] == e["year_to"] == this_year
            e["text"] = ("bisher kein Bericht im Rat gefunden" if only_now
                         else "kein Bericht im Rat gefunden")
    return out


def _recent_reports(by_plan: dict[str, list[dict]], limit: int = 4) -> list[dict]:
    """Die jüngsten Berichte über alle Pläne — ein Eintrag je Vorlage."""
    out = []
    for plan in register.PLANS.values():
        if plan.kind == "reference":
            continue
        for s in timeline(by_plan.get(plan.key, []))["stations"]:
            if s["kind"] not in REPORT_ROLES:
                continue
            out.append({"plan_key": plan.key, "plan_title": plan.title, "title": s["title"],
                        "date": s["date_end"] or s["date"], "committee": s["members"][-1]["committee"],
                        "oral": s["oral"], "kind": s["kind"], "template_number": s["template_number"],
                        "decision_id": s["decision_id"]})
    out.sort(key=lambda r: (r["date"], r["plan_title"]), reverse=True)
    return out[:limit]


def _upcoming(today: str, limit: int = 4) -> list[dict]:
    """Was die Pläne selbst als Nächstes vorsehen: Laufzeitende, Überprüfung oder Fortschreibung."""
    out = []
    for plan in register.PLANS.values():
        if plan.kind == "reference" or status(plan, today) != "running":
            continue
        if plan.end and _end_date(plan.end) >= today:
            label = f"Ende {plan.end}" if len(plan.end) == 4 else _month(plan.end)
            out.append({"plan_key": plan.key, "plan_title": plan.title, "kind": "end",
                        "date": _end_date(plan.end), "date_label": label, "text": "Laufzeit endet"})
        if plan.review_due and _end_date(plan.review_due) >= today:
            out.append({"plan_key": plan.key, "plan_title": plan.title, "kind": "review",
                        "date": _end_date(plan.review_due), "date_label": _month(plan.review_due),
                        "text": "Überprüfung oder Fortschreibung vorgesehen"})
    out.sort(key=lambda u: (u["date"], u["plan_title"]))
    return out[:limit]


# ── Die Einordnung (§ 3.3a): Berichtsstand und Stand laut Stadt ────────────

#: § 3.4 Nr. 3: Selbstauskunft kennzeichnen — und sagen, woher sie kommt.
ORIGIN_LABELS = {"template": "Nach Angaben der Verwaltung", "attachment": "Nach Angaben der Verwaltung",
                 "klimaportal": "Klimaportal der Stadt"}


def report_state_block(plan: register.Plan, items: list[dict], today: str) -> dict:
    """Der Berichtsstand samt dem einen Satz, den er braucht, wenn noch nichts fällig ist."""
    rs = plan_state.report_state(plan, items, today)
    hint = None
    if rs["state"] == "not_yet_due":
        hint = (f"Überprüfung laut Plan {_month(plan.review_due)}." if rs["due_from_plan"]
                else "Der Plan ist jünger als zwei Jahre.")
    return {"state": rs["state"], "label": rs["label"], "hint": hint}


def _status_counts(snapshot: dict) -> list[dict]:
    return [{"status_raw": c["status_raw"], "status_norm": c["status_norm"], "count": c["count"]}
            for c in snapshot["counts"]]


def status_brief(key: str) -> dict | None:
    """Die jüngste Verteilung im Wortlaut der Stadt — nur wo die Stadt eine meldet."""
    stand = plan_state.city_status(key)
    if not stand:
        return None
    s = stand["latest"]
    return {"as_of": s["as_of"], "as_of_label": _month(s["as_of"]),
            "origin_label": ORIGIN_LABELS[s["source"]["kind"]],
            "total": s["total"], "complete": s["complete"], "counts": _status_counts(s)}


def city_status_block(key: str) -> dict | None:
    """Stand laut Stadt für die Planseite: Verteilung, Bewegung, Reihe, Vorbehalte."""
    brief = status_brief(key)
    stand = plan_state.city_status(key)
    if not brief or not stand:
        return None
    s, move = stand["latest"], stand["movement"]
    src = s["source"]
    return {
        **brief,
        "source_label": src["label"],
        "source_url": src.get("url"),
        # Die Vorlage, aus der der Stand stammt — oder die ihn im Rat bestätigt.
        "template_number": src.get("template") or (s.get("confirmed_by") or {}).get("template"),
        "confirmed": bool(s.get("confirmed_by")),
        "movement": {**move, "since_label": _month(move["since"])} if move else None,
        "series": [{"as_of": x["as_of"], "as_of_label": _month(x["as_of"]), "total": x["total"],
                    "counts": _status_counts(x)} for x in stand["series"]],
        "notes": [{"text": n["text"], "url": n.get("url")} for n in stand["notes"]],
    }


def indicator_blocks(key: str) -> list[dict]:
    """KENNZAHL (§ 3.2 Nr. 5): Soll und Ist mit Bilanzjahr und Quelle, die Vorbehalte des Berichts dabei."""
    return [{
        "key": ind["key"], "label": ind["label"], "unit": ind["unit"],
        "baseline_year": ind["baseline"]["year"], "baseline_value": ind["baseline"]["value"],
        "baseline_label": ind["baseline"]["label"], "baseline_template": ind["baseline"].get("template"),
        "rows": plan_state.indicator_rows(ind),
        "notes": [{"text": n["text"], "template_number": n.get("template")} for n in ind.get("notes") or []],
    } for ind in plan_state.indicators(key)]


#: „Nicht gefunden“ statt „gibt es nicht“: Ratslotse sieht nur das Ratsinformationssystem.
NO_EVALUATION = "Eine Auswertung hat Ratslotse im Ratsinformationssystem nicht gefunden."


def review_block(plan: register.Plan, state: str, evaluation: dict | None) -> dict | None:
    """RÜCKBLICK für abgelaufene und abgelöste Pläne (§ 3.3) — ein fester Aufbau, kein freier Text:
    was vorgesehen war, was die Verwaltung meldet, welche Grenzen sie selbst nennt, was weiterläuft.

    ``evaluation``: die Vorlage, in der der Plan ausgewertet wurde (``_template_ref``)."""
    if group_of(state) != "ended":
        return None
    planned = []
    begin = plan.start or (plan.adopted.date if plan.adopted else None)
    if begin:
        planned.append({"label": "Laufzeit",
                        "value": f"{_month(begin)} bis {_month(plan.end)}" if plan.end else f"ab {_month(begin)}"})
    if listed := register.measures(plan.key):
        planned.append({"label": "Maßnahmen", "value": str(len(listed["measures"]))})
    statements = [{"kind": s["kind"], "text": s["text"], "source_label": s["source_label"],
                   "template_number": s.get("template")} for s in plan_state.review_statements(plan.key)]
    return {
        "planned": planned,
        "evaluation": evaluation,
        "no_evaluation_note": None if evaluation else NO_EVALUATION,
        "statements": statements,
        "continued_by": _neighbour(plan.successor),
        "has_status": plan_state.load(plan.key) is not None,
    }


def _card(plan: register.Plan, items: list[dict], today: str) -> dict:
    state = status(plan, today)
    latest = _latest_report(plan, items)
    note = report_note(plan, latest, state, today)
    return {
        "key": plan.key,
        "title": plan.title,
        "office": plan.office,
        "kind": plan.kind,
        "kind_label": register.KIND_LABELS[plan.kind],
        "policy_field": plan.policy_field,
        "field_label": FIELD_SHORT.get(plan.policy_field, plan.policy_field),
        "kicker": kicker(plan, items),
        "timing": timing(plan, items),
        "status": state,
        "status_label": STATUS_LABELS[state],
        "group": group_of(state),
        "adoption_mode": plan.adopted.mode if plan.adopted else None,
        "latest_report": latest,
        "report_note": note,
        "report_caveat": REPORT_CAVEAT if note and _silence_is_news(plan, today) else None,
        "lane": lane(plan, items, state, today),
        "report_count": len({_stem(i["template_number"]) or f"top{i['agenda_item_id']}"
                             for i in items if i["role"] in REPORT_ROLES}),
        "successor": _neighbour(plan.successor),
        "measure_count": len(m["measures"]) if (m := register.measures(plan.key)) else None,
        "report_state": report_state_block(plan, items, today),
        "status_brief": status_brief(plan.key),
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
    start, end = overview_axis(today)
    fields: dict[str, dict] = {}
    for c in cards:
        if c["kind"] != "reference":
            f = fields.setdefault(c["policy_field"], {"key": c["policy_field"], "label": c["field_label"], "count": 0})
            f["count"] += 1
    return {"as_of": today, "as_of_label": _datum_lang(today), "groups": groups, "references": references,
            "count": sum(len(g["plans"]) for g in groups),
            "axis": {"start": start, "end": end, "today": _pos(today, start, end),
                     "ticks": [t for t in _ticks(start, end) if int(t["label"]) % 2 == 0],
                     "fade": round(_pos(f"{int(start[:4]) + OPEN_END_YEARS}-01-01", start, end), 4)},
            "fields": sorted(fields.values(), key=lambda f: f["label"]),
            "recent": _recent_reports(by_plan),
            "upcoming": _upcoming(today)}


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


def timeline(items: list[dict], plan: register.Plan | None = None) -> dict:
    labels: dict[str, register.Decision] = {}
    if plan is not None:
        for d in ((plan.adopted,) if plan.adopted else ()) + plan.decisions:
            if d.template:
                labels[register.template_stem(d.template)] = d
    stations = []
    for g in _grouped([i for i in items if i["role"] in TIMELINE_ROLES]):
        last = g[-1]
        about = labels.get(_stem(last["template_number"]) or "") if last["role"] in ("adoption", "amendment") else None
        stations.append({
            "label": about.label if about else None,
            "mode": about.mode if about else None,
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
                    "template_number": best["template_number"], "deliberations": len(g), "measure_codes": []})
    out.sort(key=lambda e: e["date"], reverse=True)
    return out


def measures_block(key: str, links: list[dict] | None = None) -> dict | None:
    """Die geprüfte Maßnahmenliste, nach Handlungsfeld gruppiert (Reihenfolge der Quelle).

    ``links``: Beschlüsse, die eine Maßnahme nennen (``store.plan_measure_links``) —
    daraus die Zahl je Maßnahme."""
    data = register.measures(key)
    if not data:
        return None
    named: dict[str, int] = {}
    for link in links or []:
        for code in link["measure_codes"]:
            named[code] = named.get(code, 0) + 1
    stand = plan_state.city_status(key)
    states = {m["code"]: m for m in (stand["latest"].get("measures") or [])} if stand else {}
    groups: dict[str, list[dict]] = {}
    for m in data["measures"]:
        state = states.get(m["code"]) or {}
        groups.setdefault(m.get("field") or "", []).append(
            {"code": m["code"], "title": m["title"], "package": m.get("package"), "page": m["page"],
             "status_raw": state.get("status_raw"), "status_norm": state.get("status_norm"),
             "decision_count": named.get(m["code"], 0)})
    src = data["source"]
    return {
        "count": len(data["measures"]),
        "count_city": data.get("count_city"),
        "count_note": data.get("count_note"),
        # Für wie viele Maßnahmen die Stadt einen Stand nennt, und von wann.
        "status_count": len(states),
        "status_as_of_label": _month(stand["latest"]["as_of"]) if stand and states else None,
        "source": {"label": src["label"], "template_number": src.get("template"),
                   "document_id": src["document_id"], "url": src["url"],
                   "as_of": src.get("as_of"), "as_of_label": _datum_lang(src.get("as_of"))},
        "groups": [{"field": f or None, "measures": ms} for f, ms in groups.items()],
    }


def _datum_lang(iso: str | None) -> str | None:
    """``"2022-11-25"`` → ``"25.11.2022"``, ``"2024-04"`` → ``"04/2024"``."""
    if not iso:
        return None
    teile = iso.split("-")
    return ".".join(reversed(teile)) if len(teile) == 3 else _month(iso)


def detail(store, key: str, today: str | None = None) -> dict | None:
    plan = register.PLANS.get(key)
    if plan is None:
        return None
    today = today or _date.today().isoformat()
    items = store.plan_items(key)
    card = _card(plan, items, today)
    state = card["status"]
    tl = timeline(items, plan)
    tl["log"] = year_log(plan, items, state, today, tl["stations"])
    reports = [s for s in tl["stations"] if s["kind"] in REPORT_ROLES]
    groups = [{"key": k, "label": label, "entries": _entries([i for i in items if i["role"] in roles])}
              for k, label, roles in DECISION_GROUPS]
    measure_links = store.plan_measure_links(key)
    # Wer eine Maßnahme nennt, steht dort — nicht noch einmal unter den bloßen Erwähnungen.
    linked = {m["id"] for m in measure_links}
    groups.append({"key": "measures", "label": "Nennt eine Maßnahme des Plans",
                   "entries": [{"title": m["title"], "date": m["session_date"], "committee": m["committee"],
                                "decision_id": m["id"], "outcome": m["outcome"],
                                "template_number": m["template_number"], "deliberations": m["deliberations"],
                                "measure_codes": m["measure_codes"]} for m in measure_links]})
    mentions = [{"title": m["title"], "date": m["session_date"], "committee": m["committee"],
                 "decision_id": m["id"], "outcome": m["outcome"], "template_number": m["template_number"],
                 "deliberations": 1, "measure_codes": []} for m in store.plan_mentions(key) if m["id"] not in linked]
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
        "measures": measures_block(key, measure_links),
        "city_status": city_status_block(key),
        "indicators": indicator_blocks(key),
        "review": review_block(plan, state, _template_ref(store, plan.concluded, items)),
        "timeline": tl,
        "runway": runway(plan, items, state, today, tl["stations"]),
        "since": since(plan, items, state, today),
        "remaining": remaining(plan, state, today),
        "oral_report_count": sum(1 for s in reports if s["oral"]),
        "decision_groups": [g for g in groups if g["entries"]],
        "goal": plan.goal,
    }
