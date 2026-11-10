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

from council import plan_judge, plan_state
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
    if alive:
        # Ein Termin, den der Plan selbst nennt, zieht die Achse mit — höchstens so weit, wie die
        # Übersicht nach vorn schaut. „Im Jahr 2050“ stauchte sonst alles davor auf einen Daumen.
        horizon = int(today[:4]) + AXIS_YEARS_AHEAD
        named = [int(d["date"][:4]) for d in due_marks(plan, start, f"{horizon}-12-31")]
        last = max([last, *named])
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
        "dues": due_marks(plan, start, end),
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
    # Ohne Zähler keine Verteilung: Beim Mobilitätsplan zählt die Stadt den Stand nicht aus —
    # dort gibt es nur den Stand einzelner Maßnahmen, und der steht in der Maßnahmenliste.
    if not stand or not stand["latest"]["counts"]:
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
                    "counts": _status_counts(x),
                    # Was sich bis zu diesem Stand gegenüber dem vorigen bewegt hat (der erste hat keinen).
                    "movement": ({**(m := plan_state.movement(stand["series"][n - 1], x)),
                                  "since_label": _month(m["since"])} if n else None)}
                   for n, x in enumerate(stand["series"])],
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
#: Es gibt einen Stand je Maßnahme, aber keine Vorlage, die den Plan auswertet (smv2025:
#: der Stand steht in einem Anhang zu einem anderen Beschluss).
NO_EVALUATION_TEMPLATE = ("Eine eigene Vorlage zur Auswertung hat Ratslotse im Ratsinformationssystem nicht "
                          "gefunden. Den Stand der Maßnahmen nennt die Stadt in einer Anlage.")


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
    has_status = plan_state.load(plan.key) is not None
    return {
        "planned": planned,
        "evaluation": evaluation,
        "no_evaluation_note": None if evaluation else (NO_EVALUATION_TEMPLATE if has_status else NO_EVALUATION),
        "statements": statements,
        "continued_by": _neighbour(plan.successor),
        "has_status": has_status,
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
        "lane": lane(plan, items, state, today),
        "report_count": len({_stem(i["template_number"]) or f"top{i['agenda_item_id']}"
                             for i in items if i["role"] in REPORT_ROLES}),
        "successor": _neighbour(plan.successor),
        "measure_count": len(m["measures"]) if (m := register.measures(plan.key)) else None,
        "report_state": report_state_block(plan, items, today),
        "status_brief": status_brief(plan.key),
        "brief": content_brief(plan),
        "ends_on": _end_date(plan.end) if plan.end and state == "running" else None,
        "adopted_on": _start_date(plan.adopted.date) if plan.adopted else None,
        "ends_in": (rest["value"] if (rest := remaining(plan, state, today)) else None),
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


#: § 3.5: der feste Satz unter jeder Liste, die sagt, wo man nachfragen kann.
FOLLOW_UP_CAVEAT = ("Nichtöffentliche Sitzungen, Mitteilungen ohne Vorlage und Berichte außerhalb des "
                    "Ratsinformationssystems sieht Ratslotse nicht.")
#: Berichtsstände, bei denen sich eine Nachfrage anbietet (§ 3.5, Art 3).
FOLLOW_UP_STATES = ("no_report_found", "expired_no_evaluation")


def follow_ups(cards: list[dict]) -> list[dict]:
    """Wo man nachfragen kann: Pläne, zu denen kein aktueller Bericht zu finden ist.

    Angezeigt wird die Tatsache mit Datum, nie eine Wertung (§ 3.5) — und am
    längsten Stillen zuerst, nicht nach Fraktion oder Feld. Die Frage ist
    vorbereitet; stellen muss sie jemand.
    """
    out = []
    for c in cards:
        state = c["report_state"]["state"]
        if c["kind"] == "reference" or state not in FOLLOW_UP_STATES:
            continue
        out.append({
            "key": c["key"], "title": c["title"], "policy_field": c["policy_field"], "field_label": c["field_label"],
            "state": state,
            "fact": c["report_note"] or f"{c['report_state']['label']}.",
            "last_report": (c["latest_report"] or {}).get("date"),
            "question": f"Was ist aus dem Plan „{c['title']}“ geworden? Gibt es einen Bericht zum Stand der Umsetzung?",
        })
    out.sort(key=lambda f: (f["last_report"] or "", f["title"]))
    return out


#: Die Ansichten der Übersicht neben der Gliederung nach Status: je eine Auswahl in einer Reihenfolge.
#: Gerechnet wird hier; die Oberfläche legt nur die Zeilen in dieser Folge hin.
VIEW_SILENT_DAYS = 365


def views(cards: list[dict], today: str) -> list[dict]:
    """„Zuletzt berichtet“, „Endet bald“, „Lange kein Bericht“ — Schlüssel der Pläne in der Reihenfolge
    der Ansicht. Jede ist eine Tatsache mit Datum; keine reiht nach gut oder schlecht (§ 3.4)."""
    plans = [c for c in cards if c["kind"] != "reference"]

    def last(c: dict) -> str:
        return (c["latest_report"] or {}).get("date") or ""

    recent = sorted([c for c in plans if last(c)], key=lambda c: c["title"])
    recent.sort(key=last, reverse=True)
    ending = sorted([c for c in plans if c["status"] == "running" and c["ends_on"]],
                    key=lambda c: (c["ends_on"], c["title"]))
    # Still seit einem Jahr: der letzte Bericht — oder, wo es keinen gibt, der Beschluss. Am längsten Stillen zuerst.
    silent = []
    for c in plans:
        since = last(c) or c["adopted_on"]
        if c["status"] == "running" and since and _days_between(since, today) > VIEW_SILENT_DAYS:
            silent.append((since, c["title"], c))
    silent.sort(key=lambda t: t[:2])
    return [
        {"key": "recent", "label": "Zuletzt berichtet", "plans": [c["key"] for c in recent],
         "hint": "Alle Pläne mit einem Bericht im Rat, der jüngste zuerst."},
        {"key": "ending", "label": "Endet bald", "plans": [c["key"] for c in ending],
         "hint": "Laufende Pläne mit Enddatum, das nächste Ende zuerst."},
        {"key": "silent", "label": "Lange kein Bericht", "plans": [c["key"] for _s, _t, c in silent],
         "hint": "Laufende Pläne, zu denen Ratslotse seit über einem Jahr keinen Bericht im Rat gefunden hat."},
    ]


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
            "views": views(cards, today),
            "recent": _recent_reports(by_plan),
            "upcoming": _upcoming(today),
            "follow_ups": follow_ups(cards),
            "follow_up_caveat": FOLLOW_UP_CAVEAT}


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
    # Was die Verwaltung im Bericht meldet — ein Satz mit Zitat, wo es einen belegten gibt.
    said = {register.template_stem(r["template"]): r
            for r in ((plan_state.reports(plan.key) or {}).get("reports", []) if plan is not None else [])}
    stations = []
    for g in _grouped([i for i in items if i["role"] in TIMELINE_ROLES]):
        last = g[-1]
        about = labels.get(_stem(last["template_number"]) or "") if last["role"] in ("adoption", "amendment") else None
        sentence = said.get(_stem(last["template_number"]) or "") if last["role"] in REPORT_ROLES else None
        stations.append({
            "summary": {"text": sentence["text"], "quote": sentence["quote"]} if sentence else None,
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
                    "template_number": best["template_number"], "deliberations": len(g), "measure_codes": [],
                    "quote": None})
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
             # Wörtliches Zitat aus dem Bericht — nur wo ein Modell den Stand herausgesucht hat.
             "status_quote": state.get("quote"),
             "decision_count": named.get(m["code"], 0)})
    src = data["source"]
    return {
        "count": len(data["measures"]),
        "count_city": data.get("count_city"),
        "count_note": data.get("count_note"),
        # Für wie viele Maßnahmen die Stadt einen Stand nennt, und von wann.
        "status_count": len(states),
        "status_as_of_label": _month(stand["latest"]["as_of"]) if stand and states else None,
        "status_template": stand["latest"]["source"].get("template") if stand and states else None,
        # ``True``: Ein Sprachmodell hat die Stellen im Bericht gefunden; jedes Zitat ist wörtlich.
        "status_by_model": bool(stand and states and stand["latest"]["source"].get("read_by") == "model"),
        "source": {"label": src["label"], "template_number": src.get("template"),
                   "document_id": src["document_id"], "url": src["url"],
                   "as_of": src.get("as_of"), "as_of_label": _datum_lang(src.get("as_of"))},
        "groups": [{"field": f or None, "measures": ms} for f, ms in groups.items()],
    }


#: Die Überschrift des Blocks sagt, wie verbindlich der Plan ist (§ 3.4 Regel 7): „festlegt“ nur,
#: wo der Rat beschlossen hat.
CONTENT_HEADINGS = {"adopted": "Was der Plan festlegt", "noted": "Was im Plan steht",
                    "draft": "Was der Entwurf vorsieht"}
CONTENT_NOTE = ("Ein Sprachmodell hat diese Punkte aus den Dokumenten herausgesucht. Gezeigt wird nur, "
                "was als wörtliches Zitat in der Quelle steht.")
RIS_FILE = "https://buergerinfo.oldenburg.de/getfile.php?id={id}&type=do"


def _content_source(store, plan: register.Plan, ref: dict, kvonr: dict[str, int]) -> dict:
    """Der Beleg eines Kernpunkts, wie die Seite ihn zeigt: wo es steht, von wann, wohin der Link führt."""
    number = ref["template"]
    of_plan = {d.template: d for d in ((plan.adopted,) if plan.adopted else ()) + plan.decisions if d.template}
    decided = of_plan.get(number)
    date = ref.get("date") or (decided.date if decided else None)
    source = {"kind": ref["kind"], "template_number": number, "page": ref.get("page"),
              "date": date, "date_label": _datum_lang(date), "decision_id": None,
              "url": vorlage_url(kvonr.get(number))}
    if ref["kind"] == "decision":
        found = store.plan_decision_at(number, ref["date"], ref["committee"])
        noted = bool(decided and decided.mode == "noted")
        where = "des Rates" if ref["committee"] == register.COUNCIL else f"im {ref['committee']}"
        source["label"] = f"{'Kenntnisnahme' if noted else 'Beschluss'} {where}"
        source["decision_id"] = found["id"] if found else None
    elif ref["kind"] == "template":
        source["label"] = "Vorlage der Verwaltung"
    else:
        source["label"] = ref["label"]
        source["url"] = RIS_FILE.format(id=ref["document_id"]) + (f"#page={ref['page']}" if ref.get("page") else "")
    return source


#: Die Kernpunkte nach Art, in dieser Reihenfolge: Ziele oben, dann die Zahlen als Kacheln, dann Regeln,
#: dann was der Plan vorhat und bis wann. In die Kacheln kommt, was von Hand eine Zahl bekommen hat
#: (``figure``) — gleich welcher Art; der Rest verteilt sich nach Art.
CONTENT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("goals", ("goal",)),
    ("figures", ()),
    ("rules", ("standard", "responsibility")),
    ("steps", ("measure", "deadline", "figure")),
)
#: Wie eine Art heißt (Einzahl, Mehrzahl). Eine Zahl ohne Kachel steht bei den Vorhaben.
KIND_NAMES = {"goal": ("Ziel", "Ziele"), "standard": ("Regel", "Regeln"),
              "responsibility": ("Zuständigkeit", "Zuständigkeiten"), "measure": ("Vorhaben", "Vorhaben"),
              "figure": ("Vorhaben", "Vorhaben"), "deadline": ("Termin", "Termine")}
#: Das kleine Wort an der Zeile, wo eine Gruppe zwei Arten mischt.
CONTENT_TAGS = {"responsibility": "Zuständigkeit", "deadline": "Termin"}


def _group_label(key: str, kinds: list[str]) -> str:
    """„Ziele“, „Zahl“, „Regeln und Zuständigkeiten“ — die Überschrift nennt, was in der Gruppe steht."""
    if key == "figures":
        return "Zahl" if len(kinds) == 1 else "Zahlen"
    names: list[str] = []
    for kind in (k for k in KIND_NAMES if k in kinds):
        name = KIND_NAMES[kind][0 if kinds.count(kind) == 1 and len(set(kinds)) == 1 else 1]
        if name not in names:
            names.append(name)
    return " und ".join(names)


def _due_day(due: dict) -> str:
    """Der Tag, an dem ein Termin laut Plan liegt: „bis 2030“ am Jahresende, „ab 08/2026“ am Monatsersten."""
    return _start_date(due["date"]) if due.get("at") == "start" else _end_date(due["date"])


def key_point_order(points: list[dict]) -> list[tuple[str, list[int]]]:
    """Die Kernpunkte auf ihre Gruppen verteilt — je Gruppe die Stellen in der Datei, leere Gruppen fehlen."""
    out = []
    for key, kinds in CONTENT_GROUPS:
        members = [i for i, p in enumerate(points)
                   if (p.get("figure") is not None if key == "figures"
                       else p.get("figure") is None and p["kind"] in kinds)]
        if members:
            out.append((key, members))
    return out


def content_block(store, plan: register.Plan) -> dict | None:
    """Zweck und Kernpunkte des Plans (``council/plan_key_points/``) — oder ``None``, wo es keinen
    Plantext gibt. ``amended``: Der Punkt steht so in einem Beschluss NACH dem ursprünglichen Plan.

    Die Punkte kommen nach Art gegliedert (``CONTENT_GROUPS``); ``index`` ist ihre Stelle in der Datei —
    daran hängt der Sprung von der Termin-Marke im Zeitband zum Satz."""
    data = plan_state.key_points(plan.key)
    if not data:
        return None
    entries = [data["purpose"], *data["points"]]
    kvonr = store.plan_template_kvonr(sorted({e["source"]["template"] for e in entries}))
    later = {d.template for d in plan.decisions if plan.adopted and d.template and d.date > plan.adopted.date}

    def statement(entry: dict, index: int | None = None, tagged: bool = False) -> dict:
        figure, due = entry.get("figure"), entry.get("due")
        return {"text": entry["text"], "quote": entry["quote"],
                "source": _content_source(store, plan, entry["source"], kvonr),
                "amended": entry["source"]["template"] in later,
                "index": index, "kind": entry.get("kind"),
                "tag": CONTENT_TAGS.get(entry.get("kind") or "") if tagged else None,
                "figure": {"value": figure["value"], "label": figure["label"]} if figure else None,
                "due": {"date": _due_day(due), "label": due["label"]} if due else None}

    groups = []
    for key, members in key_point_order(data["points"]):
        kinds = [data["points"][i]["kind"] for i in members]
        mixed = len(set(kinds)) > 1
        groups.append({"key": key, "label": _group_label(key, kinds),
                       "layout": "tiles" if key == "figures" else "list",
                       "points": [statement(data["points"][i], i, tagged=mixed and key != "figures")
                                  for i in members]})
    purpose = statement(data["purpose"])
    # Stammt ALLES aus demselben späteren Beschluss (eine Fortschreibung), steht dessen Datum einmal
    # am Block — sechsmal dasselbe Abzeichen wäre Lärm.
    everything = [purpose, *(p for g in groups for p in g["points"])]
    dates = {s["source"]["date_label"] for s in everything}
    shared = all(s["amended"] for s in everything) and len(dates) == 1
    return {
        "heading": CONTENT_HEADINGS[plan.adopted.mode if plan.adopted else "draft"],
        "as_of_label": dates.pop() if shared else None,
        "purpose": purpose,
        "groups": groups,
        "count": len(data["points"]),
        "note": CONTENT_NOTE,
    }


def content_brief(plan: register.Plan) -> dict | None:
    """Für die aufgeklappte Zeile der Übersicht: der Zweck und die ersten zwei Kernpunkte — ohne Zitat,
    das steht auf der Planseite."""
    data = plan_state.key_points(plan.key)
    if not data:
        return None
    order = [i for _key, members in key_point_order(data["points"]) for i in members]
    return {"heading": CONTENT_HEADINGS[plan.adopted.mode if plan.adopted else "draft"],
            "purpose": data["purpose"]["text"],
            "points": [data["points"][i]["text"] for i in order[:2]],
            "count": len(data["points"])}


def due_marks(plan: register.Plan, start: str, end: str) -> list[dict]:
    """Termine, die der Plan selbst nennt (``due`` an einem Kernpunkt), als Marken auf der Achse.

    Nicht dabei: was außerhalb der Achse liegt, und ein Termin im Jahr des Laufzeitendes — das sagt
    schon das Ende des Bandes. Die Marke nennt einen Termin aus dem Plan, keine Frist von uns, und
    sagt nichts darüber, ob er gehalten wurde (§ 3.4)."""
    data = plan_state.key_points(plan.key)
    out = []
    for i, point in enumerate(data["points"] if data else []):
        due = point.get("due")
        if not due:
            continue
        day = _due_day(due)
        if not start <= day <= end or (plan.end and due.get("at") != "start" and day[:4] == plan.end[:4]):
            continue
        out.append({"x": _pos(day, start, end), "date": day, "label": due["label"], "text": point["text"],
                    "point": i})
    return sorted(out, key=lambda d: d["date"])


def sections(page: dict) -> list[dict]:
    """Die Abschnitte der Planseite für die Sprungleiste — nur was es auf DIESEM Plan gibt, in der
    Reihenfolge der Seite, mit Zähler, wo es etwas zu zählen gibt."""
    content, measures, status = page["content"], page["measures"], page["city_status"]
    decisions = sum(len(g["entries"]) for g in page["decision_groups"])
    rows = [
        ("content", "Inhalt", content["count"] if content else None, bool(content)),
        ("review", "Rückblick", None, bool(page["review"])),
        ("reports", "Berichte", page["report_count"] or None, True),
        ("status", "Stand", None, bool(status)),
        ("indicators", "Kennzahl" if len(page["indicators"]) == 1 else "Kennzahlen", None, bool(page["indicators"])),
        ("measures", "Maßnahmen", measures["count"] if measures else None, bool(measures)),
        ("places", "Karte", len(page["places"]["items"]) if page["places"] else None, bool(page["places"])),
        ("lists", "Aus dem Plan", sum(len(lst["rows"]) for lst in page["lists"]) or None, bool(page["lists"])),
        ("decisions", "Beschlüsse", decisions, decisions > 0),
    ]
    return [{"key": key, "label": label, "count": count} for key, label, count, shown in rows if shown]


#: § 3.4 Nr. 3: Selbstauskunft kennzeichnen.
NEWS_NOTE = ("Nach Angaben der Verwaltung. Ein Sprachmodell hat die Stellen herausgesucht; gezeigt wird nur, "
             "was wörtlich im jüngsten Bericht steht und im vorigen nicht.")
PLAIN_NOTE = "Automatisch aus den belegten Kernpunkten darunter umformuliert — dort steht zu jedem Satz das Zitat."


def news_block(plan: register.Plan, stations: list[dict], today: str) -> dict | None:
    """„Neu im jüngsten Bericht“: was im jüngsten Bericht einer Reihe steht und im vorigen nicht.

    Nur solange der verglichene Bericht WIRKLICH der jüngste mit Vorlage ist und nicht älter als zwei
    Jahre — „neu“ von 2022 wäre 2026 eine Irreführung. Sonst ``None``, ohne Platzhalter."""
    data = (plan_state.reports(plan.key) or {}).get("news")
    written = [s for s in stations if s["kind"] in REPORT_ROLES and s["template_number"]]
    if not data or not written:
        return None
    latest = max(written, key=lambda s: (s["date_end"] or s["date"], s["template_number"]))
    if _stem(latest["template_number"]) != register.template_stem(data["to"]):
        return None
    if _days_between(data["to_date"], today) > STALE_DAYS:
        return None
    return {"to_template": data["to"], "to_date": data["to_date"], "to_date_label": _datum_lang(data["to_date"]),
            "from_date_label": _datum_lang(data["from_date"]), "title": latest["title"],
            "decision_id": latest["decision_id"],
            "items": [{"text": i["text"], "quote": i["quote"]} for i in data["items"]], "note": NEWS_NOTE}


def plain_block(plan: register.Plan) -> dict | None:
    """Der Plan in drei einfachen Sätzen, dazu drei Fragen — nur solange die Fassung zu den HEUTIGEN
    Kernpunkten gehört (Fingerabdruck). Nach einer Änderung der Kernpunkte bleibt der Block weg, bis
    ``scripts/plan_einfach.py`` neu gelaufen ist."""
    data, points = plan_state.plain(plan.key), plan_state.key_points(plan.key)
    if not data or not points or data["based_on"] != plan_judge.plain_basis(plan_judge.key_point_lines(points)):
        return None
    return {"sentences": list(data["plain"]), "questions": list(data["questions"]), "note": PLAIN_NOTE}


#: So viele verwandte Pläne zeigt die Seite höchstens.
RELATED_MAX = 4


def related_block(plan: register.Plan, today: str) -> list[dict]:
    """Verwandte Pläne (``council/plan_related.json``): ohne Sprachmodell vorgeschlagen, von Hand
    durchgesehen. Die Seite nennt sie ohne Grad und ohne Begründung."""
    out = []
    for key in plan_state.related().get(plan.key, [])[:RELATED_MAX]:
        other = register.PLANS.get(key)
        if other is None:
            continue
        state = status(other, today)
        out.append({"key": key, "title": other.title,
                    "field_label": FIELD_SHORT.get(other.policy_field, other.policy_field),
                    "status": state, "status_label": STATUS_LABELS[state]})
    return out


# ── Orte zum Plan: Karte und Mein Viertel ─────────────────────────────────
#
# Zwei Quellen, beide ohne Sprachmodell und ohne neues Geocoding:
# - die Maßnahmenliste: Straßen und Plätze, die ein Maßnahmentitel beim Namen nennt
#   (``council/plan_places/``, von Hand durchgesehen);
# - die Beschlüsse zum Plan: Orte, die die Ortszuordnung der Ratsdaten den Umsetzungs- und
#   Berichtsbeschlüssen schon gegeben hat (``council_decision_locations``).
# Eine Karte ist keine Aussage über Fortschritt (§ 3.4): Sie zeigt, WO etwas vorgesehen ist oder
# beschlossen wurde. Den Stand trägt sie nur, wo die Stadt ihn je Maßnahme selbst meldet.

#: Was als Ort eines Plans zählt — Flächen und Stadtteile nicht: Ein Stadtteil als Punkt behauptet
#: einen Ort, der keiner ist.
PLACE_KINDS = ("street", "square", "building", "water", "facility", "structure", "route")
#: Beschlüsse, deren Orte auf die Karte dürfen: Umsetzung und Bericht — nicht die bloße Erwähnung.
PLACE_ROLES = ("implementation", "report", "evaluation")
PLACE_RELATIONS = ("implements", "names_measure")
PLACE_MIN_CONFIDENCE = 0.9
#: Katalognamen, die ein Gattungswort sind und kein Ort (der Katalog führt „Car-Sharing“ als Straße).
PLACE_GENERIC = {"gehweg", "parkplatz", "car-sharing", "radweg", "fußweg", "radschnellweg", "spielplatz",
                 "bushaltestelle", "parkhaus", "fahrradstraße"}
#: Darunter ist eine Karte Dekoration.
PLACES_MIN = 3
#: Wann eine Straße zu einem Ortsbereich zählt (Anteil am längsten Stück = 1). Eine Straße aus der
#: Maßnahmenliste meint die ganze Straße — sie zählt überall, wo ein nennenswerter Teil liegt. Nennt ein
#: Beschluss nur die Straße (eine Einrichtung „an der Alexanderstraße“), zählt nur ihr Hauptbereich:
#: Sonst stünde ein Tagesaufenthalt in fünf Stadtteilen.
AREA_SHARE_MEASURE = 0.3
AREA_SHARE_DECISION_STREET = 0.999
#: Verläufe nur bis zu dieser Größe (GeoJSON-Zeichen); darüber reicht der Punkt.
GEOMETRY_MAX = 15000
GEOMETRY_KINDS = ("street", "route", "water")
#: Fünf Nachkommastellen sind gut ein Meter — genauer zeichnet keine Karte, und die Antwort wird kleiner.
GEOMETRY_DIGITS = 5
#: Stützpunkte, die näher als das (in Grad, rund 10 m) am vorigen liegen, fallen weg — Anfang und Ende bleiben.
GEOMETRY_STEP = 0.00012
#: Die Karte eines Plans mit Gebieten aus seinen eigenen Karten (``council/plan_shapes/``).
AREAS_NOTE = "Gebiete aus den Karten im Plan, nachgezeichnet — je Gebiet mit der Stelle im Plan."
#: Beides: Abschnitte aus dem Text, Gebiete aus den Karten (Lärmaktionsplan).
SECTIONS_AREAS_NOTE = ("Abschnitte, für die der Plan einen Vorschlag macht, und Gebiete aus seinen Karten — "
                       "je mit der Stelle im Plan.")
#: Ein Gebiet zählt zu einem Ortsbereich, wenn so viel seiner Fläche dort liegt (Anteil oder Hektar).
AREA_DISTRICT_SHARE, AREA_DISTRICT_HA = 0.1, 2.0
#: Die Karte eines Plans, der seine Abschnitte selbst festlegt (``council/plan_lists/``).
SECTIONS_NOTE = "Abschnitte, für die der Plan einen Vorschlag macht — mit seinem Satz dazu und der Seite."
DECISIONS_TAIL = " Dazu Orte aus den Beschlüssen zum Plan."
SECTIONS_NOTE_DECISIONS = SECTIONS_NOTE + DECISIONS_TAIL
PLACES_NOTE = "Orte aus den Titeln der Maßnahmen und aus den Beschlüssen zum Plan."


def _geometry(row: dict):
    """Der Verlauf einer Straße — nur für Orte aus der Maßnahmenliste: „Neue Fahrradstraße Lindenallee“
    meint die Straße. Ein Beschluss, der eine Kita an der Dedestraße nennt, meint dagegen nicht die ganze
    Straße; dort reicht der Punkt."""
    raw = row.get("geojson")
    if not raw or row.get("kind") not in GEOMETRY_KINDS or len(raw) > GEOMETRY_MAX:
        return None
    import json as _json
    try:
        shape = _json.loads(raw)
    except ValueError:
        return None
    if shape.get("type") == "LineString":
        lines = [shape["coordinates"]]
    elif shape.get("type") == "MultiLineString":
        lines = shape["coordinates"]
    else:
        return None
    return {"type": "MultiLineString", "coordinates": [_thin(line) for line in lines if len(line) >= 2]}


def _thin(line: list) -> list:
    """Ein Linienzug mit weniger Stützpunkten: Was dichter als ``GEOMETRY_STEP`` am vorigen liegt, fällt
    weg; Anfang und Ende bleiben, damit die Straße nicht kürzer wird."""
    kept = [line[0]]
    for point in line[1:-1]:
        if abs(point[0] - kept[-1][0]) + abs(point[1] - kept[-1][1]) >= GEOMETRY_STEP:
            kept.append(point)
    kept.append(line[-1])
    return [[round(x, GEOMETRY_DIGITS), round(y, GEOMETRY_DIGITS)] for x, y, *_ in kept]


def plan_places(store, plan: register.Plan) -> list[dict]:
    """Die Orte eines Plans — je Ort einmal, mit den Maßnahmen und Beschlüssen, die ihn nennen."""
    by_slug: dict[str, dict] = {}

    def slot(row: dict, line: bool = False) -> dict:
        place = by_slug.setdefault(row["slug"], {
            "slug": row["slug"], "name": row["name"], "kind": row["kind"], "lat": row["lat"], "lon": row["lon"],
            "geometry": None, "measures": [], "decisions": [], "sections": [], "areas": []})
        if line and place["geometry"] is None:
            place["geometry"] = _geometry(row)
        return place

    # Abschnitte, die der Plan selbst festlegt (Lärmaktionsplan): mit Verlauf, Vorschlag und Seite.
    # ``districts`` rechnet ``scripts/plan_listen.py`` mit; die Seite gibt es nicht aus.
    listed_doc = plan_state.plan_lists(plan.key)
    if listed_doc:
        url = RIS_FILE.format(id=listed_doc["document"]["document_id"])
        for s in listed_doc.get("sections", []):
            by_slug[f"abschnitt-{s['code']}"] = {
                "slug": f"abschnitt-{s['code']}", "name": s["name"], "kind": "street", "lat": s["lat"],
                "lon": s["lon"], "geometry": s["geometry"], "measures": [], "decisions": [], "areas": [],
                "sections": [{"code": s["code"], "stretch": s["stretch"], "quote": s["quote"], "page": s["page"],
                              "source_url": f"{url}#page={s['page']}"}],
                "districts": s["districts"]}
    # Gebiete, nachgezeichnet aus den Kartenbildern des Plans (Wärmeplan): als Fläche.
    shapes = plan_state.plan_shapes(plan.key)
    if shapes:
        by_slug.update({p["slug"]: p for p in _shape_places(shapes)})
    named = plan_state.measure_places(plan.key)
    if named:
        listed = register.measures(plan.key) or {"measures": []}
        titles = {m["code"]: m["title"] for m in listed["measures"]}
        stand = plan_state.city_status(plan.key)
        states = {m["code"]: m for m in (stand["latest"].get("measures") or [])} if stand else {}
        catalog = store.plan_catalog_places([p["slug"] for e in named["measures"] for p in e["places"]])
        for entry in named["measures"]:
            for place in entry["places"]:
                row = catalog.get(place["slug"])
                if row is None or entry["code"] not in titles:
                    continue
                state = states.get(entry["code"]) or {}
                slot(row, line=True)["measures"].append({"code": entry["code"], "title": titles[entry["code"]],
                                              "status_raw": state.get("status_raw"),
                                              "status_norm": state.get("status_norm")})
    rows = store.plan_decision_places(plan.key, PLACE_ROLES, PLACE_RELATIONS, PLACE_KINDS, PLACE_MIN_CONFIDENCE)
    # Nennt ein Beschluss eine Adresse („Bahnweg 84“), steht die Straße („Bahnweg“) nicht noch einmal da.
    addresses: dict[int, list[str]] = {}
    for r in rows:
        if r["kind"] == "building":
            addresses.setdefault(r["decision_id"], []).append(r["name"].lower())
    for r in rows:
        if r["name"].lower() in PLACE_GENERIC:
            continue
        if r["kind"] == "street" and any(a.startswith(r["name"].lower() + " ") for a in addresses.get(r["decision_id"], [])):
            continue
        decisions = slot(r)["decisions"]
        if all(d["id"] != r["decision_id"] for d in decisions):
            decisions.append({"id": r["decision_id"], "title": r["title"], "date": r["session_date"]})
    out = list(by_slug.values())
    for place in out:
        place["decision_count"] = len(place["decisions"])
        place["decisions"] = place["decisions"][:3]
    # Abschnitte, dann Gebiete (in der Reihenfolge der Datei), dann der Rest.
    out.sort(key=lambda p: (0 if p["sections"] else 1 if p["areas"] else 2,
                            p["sections"][0]["code"] if p["sections"] else p["areas"][0]["order"] if p["areas"] else "",
                            -len(p["measures"]) - p["decision_count"], p["name"]))
    return out


def _area_name(shapes: dict, p: dict) -> str:
    """So heißt ein Gebiet auf der Karte: „WNG 7 Kennedyviertel“ (Wärmeplan: Kennung gehört zum Namen) oder
    „Huntewiesen“."""
    if not p.get("name"):
        return p["code"]
    return f"{p['code']} {p['name']}" if shapes.get("code_in_name") else p["name"]


def _area_label(group: str, name: str, p: dict) -> str:
    """So steht ein Gebiet im Viertel: „Ruhiges Gebiet „Huntewiesen““ — ohne die Gruppe zu doppeln, wo der
    Name sie schon trägt („Waldfriedhof Ofenerdiek“). Eine Datei kann es je Gebiet selbst setzen."""
    if p.get("label"):
        return p["label"]
    return name if group.lower() in name.lower() else f"{group} „{name}“"


def _shape_places(shapes: dict) -> list[dict]:
    """Je Gebiet aus ``council/plan_shapes/`` ein Ort — mit Fläche oder, wo der Plan nur einen Standort
    zeigt, als Punkt. Den vereinfachten Umriss und den Beschriftungspunkt legen ``scripts/plan_umrisse.py``
    und ``scripts/plan_karten.py`` in die Datei; der Server rechnet nicht."""
    url = RIS_FILE.format(id=shapes["document"]["document_id"])
    word = shapes.get("figure_word", "Abb.")
    out = []
    for i, f in enumerate(shapes["features"]):
        p = f["properties"]
        lon, lat = p["label_point"]
        ha = p.get("area_ha")
        # Ortsbereiche: wo ein nennenswerter Teil der Fläche liegt — gerechnet, nicht aus der Ortsteil-Spalte.
        districts = {pid: 1.0 for pid, share in p["districts"].items()
                     if ha is None or share >= AREA_DISTRICT_SHARE or share * ha >= AREA_DISTRICT_HA}
        name = _area_name(shapes, p)
        group = p.get("group") or shapes.get("group") or "Gebiet"
        figure = p.get("figure")

        def link(page):
            return f"{url}#page={page}" if page else None
        out.append({
            "slug": "gebiet-" + p["code"].lower().replace(" ", "-"), "name": name, "kind": "area",
            "lat": lat, "lon": lon, "geometry": p["display_geometry"],
            "measures": [], "decisions": [], "sections": [],
            "areas": [{"code": p["code"], "group": group, "label": _area_label(group, name, p),
                       "figure": figure, "page": p["page"],
                       "source_label": f"{word} {figure}, S. {p['page']}" if figure else f"S. {p['page']}",
                       "source_url": p.get("source_url") or f"{url}#page={p['page']}",
                       "area_ha": ha, "area_ha_plan": p.get("area_ha_plan"), "order": f"{i:03d}",
                       "summary": p.get("summary"), "radius_m": p.get("radius_m"),
                       "facts": [{**f_, "source_url": link(f_.get("page"))} for f_ in p.get("facts", [])],
                       "notes": [{**n, "source_url": link(n.get("page"))} for n in p.get("notes", [])]}],
            "districts": districts})
    return out


#: So viele Arten unterscheidet die Karte am Rand (durchgezogen, gestrichelt, gepunktet, Strich-Punkt) —
#: eine Farbe für alle, die Seite färbt nicht nach Art (Designsprache: Primärtönung).
AREA_STYLES = 4


def _area_groups(shapes: dict | None, places: list[dict]) -> list[dict]:
    """Die Arten der Gebiete in der Reihenfolge ihres ersten Auftretens — mit dem, was der Plan darunter
    versteht (``groups`` der Datei), und dem Randstil auf der Karte."""
    seen: list[str] = []
    for p in places:
        if p["areas"] and p["areas"][0]["group"] not in seen:
            seen.append(p["areas"][0]["group"])
    known = (shapes or {}).get("groups", {})
    return [{"name": name, "description": known.get(name, {}).get("description"),
             "page": known.get(name, {}).get("page"), "source_url": known.get(name, {}).get("source_url"),
             "sites_only": all(p["geometry"] is None for p in places if p["areas"] and p["areas"][0]["group"] == name),
             "style": i % AREA_STYLES} for i, name in enumerate(seen)]


def places_block(store, plan: register.Plan) -> dict | None:
    """Die Karte zum Plan — ab ``PLACES_MIN`` Orten, sonst ``None`` (kein Platzhalter)."""
    places = plan_places(store, plan)
    if len(places) < PLACES_MIN:
        return None
    listed = register.measures(plan.key)
    decision_places = sum(1 for p in places if p["decision_count"])
    with_sections = sum(1 for p in places if p["sections"])
    with_areas = sum(1 for p in places if p["areas"])
    note = PLACES_NOTE
    if with_sections or with_areas:
        note = (SECTIONS_AREAS_NOTE if with_sections and with_areas else SECTIONS_NOTE if with_sections
                else AREAS_NOTE) + (DECISIONS_TAIL if decision_places else "")
    return {
        "items": [{k: v for k, v in p.items() if k != "districts"} for p in places],
        "groups": _area_groups(plan_state.plan_shapes(plan.key), places),
        "section_places": with_sections,
        "area_places": with_areas,
        "geojson": bool(with_sections or with_areas),
        "measure_places": sum(1 for p in places if p["measures"]),
        "measures_named": len({m["code"] for p in places for m in p["measures"]}),
        "measures_total": len(listed["measures"]) if listed else None,
        "decision_places": decision_places,
        "note": note,
    }


def geojson_export(store, plan: register.Plan) -> dict | None:
    """Alle Abschnitte und Gebiete, die der Plan selbst festlegt, als GeoJSON (WGS84) — die Gebiete in
    voller Auflösung der Datei. ``None``: Der Plan hat keine."""
    lists, shapes = plan_state.plan_lists(plan.key) or {}, plan_state.plan_shapes(plan.key) or {}
    features = []
    for s in lists.get("sections", []):
        url = RIS_FILE.format(id=lists["document"]["document_id"])
        features.append({"type": "Feature", "geometry": s["geometry"], "properties": {
            "kind": "section", "code": s["code"], "street": s["name"], "stretch": s["stretch"], "quote": s["quote"],
            "page": s["page"], "source_url": f"{url}#page={s['page']}", "length_m": s["length_m"]}})
    for place, f in zip(_shape_places(shapes) if shapes else [], shapes.get("features", [])):
        a = place["areas"][0]
        features.append({"type": "Feature", "geometry": f["geometry"], "properties": {
            "kind": "area" if f["geometry"]["type"] != "Point" else "site", "code": a["code"], "name": place["name"],
            "group": a["group"], "figure": a["figure"], "page": a["page"], "source_url": a["source_url"],
            "area_ha": a["area_ha"], "area_ha_plan": a["area_ha_plan"], "summary": a["summary"],
            "facts": a["facts"]}})
    if not features:
        return None
    sources = []
    if lists and lists.get("sections"):
        sources.append(f"{plan.title}: {lists['document']['label']}, Kapitel 18; Linien © OpenStreetMap-Mitwirkende, ODbL")
    if shapes:
        sources.append(f"{shapes['name']}: nachgezeichnet aus {shapes['document']['label']}; {shapes['attribution']}")
    return {"type": "FeatureCollection", "name": plan.title, "attribution": "; ".join(sources),
            "generated": (shapes or lists or {}).get("generated"), "features": features}


def lists_block(plan: register.Plan) -> list[dict]:
    """Tabellen aus dem Plan-Dokument (``council/plan_lists/``) — Zeile für Zeile, wie sie dort stehen,
    mit der Seite."""
    data = plan_state.plan_lists(plan.key)
    if not data:
        return []
    url = RIS_FILE.format(id=data["document"]["document_id"])
    return [{
        "key": lst["key"], "title": lst["title"], "caption": lst["caption"], "page": lst["page"],
        "source_label": data["document"]["label"], "source_url": f"{url}#page={lst['page']}",
        "columns": list(lst["columns"]), "name_column": lst["name_column"],
        "rows": [{"cells": list(r["cells"]), "page": r.get("page"),
                  "source_url": f"{url}#page={r['page']}" if r.get("page") else None} for r in lst["rows"]],
    } for lst in data.get("lists", [])]


def _counts_here(place: dict, share: float | None) -> bool:
    """Gehört ein Ort des Plans zu diesem Ortsbereich (``share``: sein Anteil dort, ``None``: gar nicht)?"""
    if share is None:
        return False
    if place.get("areas"):
        return True  # schon beim Laden gefiltert (AREA_DISTRICT_SHARE, AREA_DISTRICT_HA)
    if place["measures"] or place.get("sections"):
        return share >= AREA_SHARE_MEASURE
    return share >= AREA_SHARE_DECISION_STREET if place["kind"] == "street" else True


def district_plans(store, place_id: str, today: str | None = None) -> list[dict]:
    """„Pläne, die dein Viertel betreffen“: laufende und entstehende Pläne mit mindestens einem Ort in
    diesem Ortsbereich — mit den Orten, über die sie hierher gehören. Nichts geschätzt: nur Orte aus
    Maßnahmentiteln und Beschlüssen (s. :func:`plan_places`)."""
    today = today or _date.today().isoformat()
    found = []
    for plan in register.PLANS.values():
        if plan.kind == "reference":
            continue
        state = status(plan, today)
        if group_of(state) == "ended":
            continue
        places = plan_places(store, plan)
        # Gebiete aus einer Tabelle des Plans, die ihren Ortsteil nennt (Wärmeplan, Tabelle 4) — nur, wo es
        # keine nachgezeichneten Umrisse gibt: Die Fläche weiß es genauer als die Spalte.
        rows = [] if plan_state.plan_shapes(plan.key) else [
            r for lst in (plan_state.plan_lists(plan.key) or {}).get("lists", [])
            for r in lst["rows"] if place_id in r.get("districts", [])]
        if not places and not rows:
            continue
        areas = store.plan_place_areas([p["slug"] for p in places if "districts" not in p])
        here = [p for p in places
                if _counts_here(p, (p.get("districts") or areas.get(p["slug"], {})).get(place_id))]
        # „Bahnweg“ neben „Bahnweg 84“ sagt nichts Neues: Die Straße fällt, wo eine Adresse an ihr steht.
        names = [p["name"] for p in here]
        here = [p for p in here if not (p["kind"] == "street" and any(n.startswith(p["name"] + " ") for n in names))]
        if not here and not rows:
            continue
        labels = [r["label"] for r in rows] + [p["areas"][0]["label"] if p["areas"] else p["name"] for p in here]
        found.append({"key": plan.key, "title": plan.title,
                      "field_label": FIELD_SHORT.get(plan.policy_field, plan.policy_field),
                      "status": state, "status_label": STATUS_LABELS[state],
                      "places": labels[:4], "place_count": len(labels),
                      "via_measures": any(p["measures"] for p in here)})
    found.sort(key=lambda f: (-f["place_count"], f["title"]))
    return found


# ── Haushalt zum Plan (nur mit dem Recht ``budget``) ───────────────────────

#: So heißen die Änderungslisten (wie in web/frontend/lib/haushalt-aenderungslisten.ts).
BUDGET_LISTS = {"administration_1": "Änderungsliste der Verwaltung I",
                "administration_2": "Änderungsliste der Verwaltung II",
                "administration_3": "Änderungsliste der Verwaltung III",
                "fc_decided": "Beschlossene Änderungen (Finanzausschuss)"}
#: Spätere Stufen einer Änderung ersetzen frühere: Was der Finanzausschuss beschlossen hat, zählt.
BUDGET_LIST_ORDER = ("administration_1", "administration_2", "administration_3", "fc_decided")
BUDGET_NOTE = "Haushaltsposten, deren eigener Text den Plan beim Namen nennt."


def _budget_quote(text: str, pattern: str) -> str:
    """Die Stelle, an der der Plan genannt ist — der Satz darum, höchstens 300 Zeichen."""
    import re as _re
    flat = " ".join((text or "").split())
    m = _re.search(pattern, flat, _re.I)
    if not m:
        return flat[:300]
    dot = flat.rfind(". ", 0, m.start())
    start = max(dot + 2 if dot >= 0 else 0, m.start() - 160)
    if start > 0 and flat[start - 1] != " ":
        # Nicht mitten im Wort anfangen: zum nächsten Wortanfang.
        space = flat.find(" ", start)
        start = space + 1 if 0 <= space < m.start() else start
    end = flat.find(". ", m.end())
    end = len(flat) if end < 0 else end + 1
    if end > m.end() + 160:
        space = flat.rfind(" ", m.end(), m.end() + 160)
        end = space if space > m.end() else m.end() + 160
    cut_front = start > 0 and dot + 2 != start
    return ("…" if cut_front else "") + flat[start:end].strip() + ("…" if end < len(flat) and flat[end - 1] != "." else "")


def budget_block(store, plan: register.Plan) -> dict:
    """Was im Haushalt den Plan nennt (``council/plan_budget.json``) — Beträge so, wie sie in der Zeile
    stehen, ungerundet; gerundet wird einmal, in der Anzeige. Produkte mit dem jüngsten Ansatz, der den
    Plan nennt; Investitionen je Programmjahr; Änderungen je Planjahr, die spätere Liste ersetzt die
    frühere."""
    refs = plan_state.budget_refs().get(plan.key, [])
    pattern = plan_state.budget_patterns().get(plan.key, "")
    items: list[dict] = []
    changes: dict[tuple, dict] = {}
    for ref in refs:
        rows = store.plan_budget_rows(ref["table"], ref)
        if "years" in ref:
            rows = [r for r in rows if r["year"] in ref["years"]]
        if not rows:
            continue
        if ref["table"] == "products":
            row = max(rows, key=lambda r: r["year"])
            items.append({"kind": "product", "title": row["product_name"], "number": row["product_no"],
                          "context": f"Teilhaushalt {row['sub_budget_name']}" if row.get("sub_budget_name") else None,
                          "quote": _budget_quote(row.get(ref["field"]) or "", pattern),
                          "amounts": [{"label": f"Aufwand {row['year']} (Ansatz)", "value": row["expenses"]},
                                      {"label": f"Ertrag {row['year']} (Ansatz)", "value": row["revenues"]}],
                          "since": min(r["year"] for r in rows), "source_url": row.get("source_url")})
        elif ref["table"] == "investments":
            ordered = sorted(rows, key=lambda r: r["year"])
            items.append({"kind": "investment", "title": ordered[-1]["label"], "number": ordered[-1]["code"],
                          "context": "Investitionsprogramm",
                          "quote": _budget_quote(ordered[-1].get(ref["field"]) or "", pattern),
                          "amounts": [{"label": f"Programm {r['year']}", "value": r["grand_total"]} for r in ordered],
                          "since": ordered[0]["year"], "source_url": None})
        else:
            row = rows[0]
            cash = ref["table"] == "amendments_cash"
            value = (row.get("outflow") if row.get("outflow") is not None else row.get("inflow")) if cash else \
                (row.get("expense") if row.get("expense") is not None else row.get("revenue"))
            what = ("Auszahlung" if row.get("outflow") is not None else "Einzahlung") if cash else \
                ("Aufwand" if row.get("expense") is not None else "Ertrag")
            group = (ref["table"], row["budget_year"], row["label"], " ".join((row.get("explanation") or "").split()))
            slot = changes.setdefault(group, {"stages": {}, "row": row, "what": what, "field": ref["field"]})
            slot["stages"].setdefault(row["list_key"], {})[row["year"]] = value
    for (table, budget_year, label, _text), slot in changes.items():
        stage = max(slot["stages"], key=lambda k: BUDGET_LIST_ORDER.index(k) if k in BUDGET_LIST_ORDER else -1)
        row = slot["row"]
        items.append({"kind": "change", "title": label, "number": row.get("product"),
                      "context": f"{BUDGET_LISTS.get(stage, stage)}, Haushalt {budget_year}",
                      "quote": _budget_quote(row.get(slot["field"]) or "", pattern),
                      "amounts": [{"label": f"{slot['what']} {year}", "value": value}
                                  for year, value in sorted(slot["stages"][stage].items()) if value is not None],
                      "since": budget_year,
                      "source_url": RIS_FILE.format(id=row["document_id"]) if row.get("document_id") else None})
    order = {"product": 0, "investment": 1, "change": 2}
    items.sort(key=lambda i: (order[i["kind"]], -(i["since"] or 0), i["title"]))
    return {"items": items, "note": BUDGET_NOTE}


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
                                "measure_codes": m["measure_codes"], "quote": None} for m in measure_links]})
    # Vorlagen, die laut ihrem eigenen Text der Umsetzung dienen (Phase 4 Teil 2) — mit dem Satz, der es sagt.
    # Wer schon bei einer Maßnahme steht, steht nur dort.
    quotes = {register.template_stem(link["template"]): link["quote"] for link in plan_state.judged_links(key)}
    stems_named = {register.template_stem(m["template_number"]) for m in measure_links}
    judged = [m for m in store.plan_judged_links(key) if register.template_stem(m["template_number"]) not in stems_named]
    groups.append({"key": "judged", "label": "Dient laut Vorlage der Umsetzung des Plans",
                   "entries": [{"title": m["title"], "date": m["session_date"], "committee": m["committee"],
                                "decision_id": m["id"], "outcome": m["outcome"],
                                "template_number": m["template_number"], "deliberations": m["deliberations"],
                                "measure_codes": [], "quote": quotes.get(register.template_stem(m["template_number"]))}
                               for m in judged]})
    shown = {register.template_stem(m["template_number"]) for m in judged} | stems_named
    mentions = [{"title": m["title"], "date": m["session_date"], "committee": m["committee"],
                 "decision_id": m["id"], "outcome": m["outcome"], "template_number": m["template_number"],
                 "deliberations": 1, "measure_codes": [], "quote": None} for m in store.plan_mentions(key)
                if m["id"] not in linked and register.template_stem(m["template_number"]) not in shown]
    groups.append({"key": "mentions", "label": "Erwähnt den Plan über seine Vorlagennummer",
                   "entries": mentions})
    page = {
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
        "content": content_block(store, plan),
        "plain": plain_block(plan),
        "news": news_block(plan, tl["stations"], today),
        "related": related_block(plan, today),
        "places": places_block(store, plan),
        "lists": lists_block(plan),
        "measures": measures_block(key, measure_links),
        "city_status": city_status_block(key),
        "indicators": indicator_blocks(key),
        "review": review_block(plan, state, _template_ref(store, plan.concluded, items)),
        "website": register.website(key),
        "timeline": tl,
        "runway": runway(plan, items, state, today, tl["stations"]),
        "since": since(plan, items, state, today),
        "remaining": remaining(plan, state, today),
        "oral_report_count": sum(1 for s in reports if s["oral"]),
        "decision_groups": [g for g in groups if g["entries"]],
        "goal": plan.goal,
    }
    page["sections"] = sections(page)
    return page
