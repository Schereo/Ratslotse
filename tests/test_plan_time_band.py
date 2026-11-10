"""Pläne der Stadt: das Zeitband — wann ein Plan gilt und wann berichtet wurde.

Die Oberfläche zeichnet jeden Plan als Strecke auf einer Zeitachse
(``council/plan_pages.py``, Abschnitt „Zeitband“). Gerechnet wird im Backend,
damit Web und App dasselbe zeigen. Festgehalten ist hier, was das Band SAGT:

- **Es ist kein Fortschrittsbalken** (Plan § 3.4): Lage und Länge kommen aus
  Beschluss und Laufzeitende, nie aus einem Umsetzungsstand.
- **Ohne Enddatum endet es heute und läuft aus**, statt ein Ende zu behaupten.
- **„Zur Kenntnis“ und „in Arbeit“ tragen eine eigene Form** — die Kenntnisnahme
  ist kein Beschluss (Regel 7).
- **Eine Lücke im Zeitstrahl ist „keinen gefunden“**: erst nach dem Jahr des
  Beschlusses, frühestens ab 2018 (Beginn des Bestands), und im laufenden Jahr
  mit „bisher“.
"""
from __future__ import annotations

from council import plan_pages, plans

TODAY = "2026-11-09"
P = plans.PLANS


def _item(i: int, date: str, role: str, template: str | None = None, *, oral: bool = False,
          committee: str = "Rat", title: str = "Bericht") -> dict:
    return {"plan_key": "x", "agenda_item_id": i, "date": date, "committee": committee, "title": title,
            "template_number": template, "role": role, "oral": int(oral), "decision_id": None, "outcome": None}


def _lane(key: str, items: list[dict] | None = None, today: str = TODAY) -> dict:
    plan = P[key]
    return plan_pages.lane(plan, items or [], plan_pages.status(plan, today), today)


def _log(key: str, items: list[dict], today: str = TODAY) -> list[tuple]:
    plan = P[key]
    stations = plan_pages.timeline(items, plan)["stations"]
    log = plan_pages.year_log(plan, items, plan_pages.status(plan, today), today, stations)
    return [(e["kind"], e["year"], e["year_to"], e["text"]) for e in log]


# ── Rechnen mit Tagen ─────────────────────────────────────────────────────

def test_month_end_is_a_real_day():
    # „2029-09-31“ gibt es nicht — das Band rechnet mit dem Tag, ein Vergleich von Zeichenketten nicht.
    assert plan_pages._end_date("2029-09") == "2029-09-30"
    assert plan_pages._end_date("2028-02") == "2028-02-29"
    assert plan_pages._end_date("2035") == "2035-12-31"


def test_duration_in_words():
    assert plan_pages.duration(46) == "3 Jahre, 10 Monate"
    assert plan_pages.duration(13) == "1 Jahr, 1 Monat"
    assert plan_pages.duration(12) == "1 Jahr"
    assert plan_pages.duration(5) == "5 Monate"
    assert plan_pages.duration(0) == "weniger als ein Monat"
    # Ab fünf Jahren ohne Monate: „9 Jahre, 1 Monat“ wäre Scheinpräzision.
    assert plan_pages.duration(109) == "9 Jahre"


def test_since_adoption_and_time_remaining():
    ksp = P["klimaschutzplan_2035"]
    assert plan_pages.since(ksp, [], "running", TODAY) == {"label": "Seit dem Beschluss", "value": "3 Jahre, 10 Monate"}
    assert plan_pages.remaining(ksp, "running", TODAY) == {"label": "Laufzeit noch", "value": "9 Jahre"}
    # Zur Kenntnis genommen ist nicht beschlossen — auch nicht im Etikett.
    assert plan_pages.since(P["demografiestrategie"], [], "running", TODAY)["label"] == "Seit der Kenntnisnahme"
    # Abgelöste Pläne zählen nicht weiter, und ohne Enddatum gibt es kein „noch“.
    assert plan_pages.since(P["aktionsplan_gewalt_2020"], [], "superseded", TODAY) is None
    assert plan_pages.remaining(P["masterplan_stadtgruen"], "running", TODAY) is None


# ── Das Band der Übersicht ────────────────────────────────────────────────

def test_band_runs_from_start_to_end_of_term():
    lane = _lane("klimaschutzplan_2035")
    band = lane["band"]
    assert lane["style"] == "adopted"
    assert 0.25 < band["x0"] < 0.27 and 0.94 < band["x1"] < 0.95   # 12/2022 bis Ende 2035 auf 2018–2036
    assert not band["open_end"] and not band["open_start"] and not band["beyond"]
    assert 0.49 < lane["review"] < 0.51                             # Überprüfung 2027
    # Der Vorgänger (Aktionsplan Energie 2019/2020) läuft als Spur davor.
    assert lane["predecessor"]["x1"] < band["x0"]


def test_band_without_end_date_stops_today():
    axis = plan_pages.overview_axis(TODAY)
    today_x = plan_pages._pos(TODAY, *axis)
    band = _lane("masterplan_stadtgruen")["band"]
    assert band["open_end"] is True and band["x1"] == today_x


def test_noted_and_preparing_have_their_own_look():
    assert _lane("demografiestrategie")["style"] == "noted"
    preparing = P["klimaanpassungskonzept"]
    first = [_item(1, "2024-12-05", "report", preparing.commissioned)]
    lane = _lane("klimaanpassungskonzept", first)
    assert lane["style"] == "preparing" and lane["band"]["open_end"] is False
    # Leerer Bestand (CI): kein Beginn bekannt, also kein Band — und kein Fehler.
    assert _lane("klimaanpassungskonzept")["band"] is None


def test_band_beyond_the_axis():
    assert _lane("kita_ausbau")["band"]["open_start"] is True         # beschlossen 2008
    assert _lane("kita_ausbau")["band"]["x0"] == 0
    assert _lane("digitalisierungsstrategie")["band"]["beyond"] is True  # Vision bis 2045


def test_preparation_marks_only_on_the_runway():
    plan = P["klimaschutzplan_2035"]
    items = [_item(1, "2022-02-10", "preparation", "22/0037"),
             _item(2, "2022-12-19", "adoption", "22/0910"),
             _item(3, "2026-10-08", "report", "26/0750"),
             _item(4, "2025-03-05", "report", None, oral=True)]
    kinds = [m["kind"] for m in plan_pages.lane(plan, items, "running", TODAY)["marks"]]
    assert "preparation" not in kinds and sorted(kinds) == ["adoption", "report", "report"]
    stations = plan_pages.timeline(items, plan)["stations"]
    strip = plan_pages.runway(plan, items, "running", TODAY, stations)
    assert [m["kind"] for m in strip["marks"]] == ["preparation", "adoption", "report", "report"]
    assert [m["station"] for m in strip["marks"]] == [0, 1, 2, 3]
    assert strip["marks"][2]["oral"] is True
    assert strip["start"] == "2022-01-01" and strip["end"] == "2035-12-31"
    assert 0 < strip["today"] < 1 and strip["archive_from"] is None


def test_before_2018_the_data_is_missing_not_the_reports():
    plan = P["kita_ausbau"]
    items = [_item(1, "2018-08-15", "report", "18/0526")]
    stations = plan_pages.timeline(items, plan)["stations"]
    strip = plan_pages.runway(plan, items, "running", TODAY, stations)
    assert strip["start"] == "2008-01-01"
    assert 0.4 < strip["archive_from"] < 0.45      # 2018 auf der Achse 2008–2030


# ── Lücken im Zeitstrahl ──────────────────────────────────────────────────

def test_years_without_report_merge_into_one_gap():
    items = [_item(1, "2022-09-26", "adoption", "22/0642"),
             _item(2, "2023-06-08", "report", None, oral=True),
             _item(3, "2024-02-08", "report", None, oral=True)]
    assert _log("masterplan_stadtgruen", items) == [
        ("gap", 2025, 2026, "kein Bericht im Rat gefunden"),
        ("year", 2024, 2024, None), ("year", 2023, 2023, None), ("year", 2022, 2022, None)]


def test_current_year_is_not_over_yet():
    items = [_item(1, "2022-09-26", "adoption", "22/0642"), _item(2, "2025-11-19", "report", "25/0765")]
    log = _log("masterplan_stadtgruen", items)
    assert log[0] == ("gap", 2026, 2026, "bisher kein Bericht im Rat gefunden")


def test_no_gap_in_the_year_of_adoption():
    items = [_item(1, "2026-06-01", "adoption", "26/0236")]
    assert _log("waermeplan", items) == [("year", 2026, 2026, None)]


def test_gaps_start_no_earlier_than_2018():
    # 2009 beschlossen: Davor kennt das Ratsinformationssystem keine Sitzungen.
    items = [_item(1, "2019-11-13", "report", None, oral=True)]
    assert _log("sportentwicklungsplan_2009", items) == [
        ("gap", 2020, 2026, "kein Bericht im Rat gefunden"),
        ("year", 2019, 2019, None),
        ("gap", 2018, 2018, "kein Bericht im Rat gefunden")]


def test_superseded_plan_counts_only_until_its_end():
    items = [_item(1, "2020-09-28", "adoption", "20/0564"), _item(2, "2021-09-28", "report", "21/0704")]
    log = _log("aktionsplan_gewalt_2020", items)
    assert log[0] == ("gap", 2022, 2025, "kein Bericht im Rat gefunden")   # Laufzeit bis 2025, nicht bis heute


# ── Der Kopf der Übersicht ────────────────────────────────────────────────

def test_upcoming_dates_from_the_plans():
    upcoming = plan_pages._upcoming(TODAY, limit=50)
    assert upcoming[0]["plan_key"] == "gleichstellungsplan_2024" and upcoming[0]["date_label"] == "Ende 2026"
    assert [u["date"] for u in upcoming] == sorted(u["date"] for u in upcoming)
    assert all(u["date"] >= TODAY for u in upcoming)
    assert {"klimaschutzplan_2035", "review"} in [{u["plan_key"], u["kind"]} for u in upcoming]
    # Nach dem Laufzeitende steht der Plan nicht mehr unter „als Nächstes“.
    assert "gleichstellungsplan_2024" not in {u["plan_key"] for u in plan_pages._upcoming("2027-01-02", limit=50)}


class _EmptyStore:
    def plan_items(self, key=None):
        return []


def test_overview_has_axis_and_fields_without_data():
    o = plan_pages.overview(_EmptyStore(), TODAY)
    axis = o["axis"]
    assert axis["start"] == "2018-01-01" and axis["end"] == "2036-12-31"
    assert 0.46 < axis["today"] < 0.47
    assert [t["label"] for t in axis["ticks"]] == [str(j) for j in range(2018, 2037, 2)]
    assert sum(f["count"] for f in o["fields"]) == o["count"]
    assert o["recent"] == [] and len(o["upcoming"]) == 4
    cards = [c for g in o["groups"] for c in g["plans"]]
    assert all(c["lane"]["marks"] == [] for c in cards)
    # Die Lücke steht als Tatsache da, ohne Einordnung dahinter.
    by_key = {c["key"]: c for c in cards}
    assert by_key["waermeplan"]["report_note"] and "report_caveat" not in by_key["waermeplan"]
