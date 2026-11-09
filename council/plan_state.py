"""Stand der Pläne: geprüfte Momentaufnahmen und was sich daraus sagen lässt.

docs/plan-ziele-plaene.md § 3.3a. Die Einordnung je Plan besteht aus drei
Bausteinen, und keiner davon bewertet:

1. **Berichtsstand** — wird über den Plan berichtet? (:func:`report_state`)
2. **Stand laut Stadt** — die Verteilung im Wortlaut der Stadt, mit Datum und
   Beleg, und was sich seit dem vorigen Bericht bewegt hat (:func:`city_status`)
3. **Eigene Termine** — Laufzeit und Überprüfungsfrist als Tatsachen
   (:func:`own_dates`)

Die Momentaufnahmen liegen als geprüfte Dateien unter ``council/plan_status/``
(geschrieben von ``scripts/plan_status.py``, festgehalten im PR). ``status_norm``
dient nur zum Gruppieren und für den Farbton — angezeigt wird immer
``status_raw``, das Wort der Stadt.

Hier wird nur gerechnet. Sätze und Antwortform baut ``council/plan_pages.py``.
"""
from __future__ import annotations

import calendar
import json
from datetime import date, timedelta
from functools import cache
from pathlib import Path

from council import plans as register

STATUS_DIR = Path(__file__).resolve().parent / "plan_status"

#: Fünf Stufen plus „unklar“. Reihenfolge = Reihenfolge der Anzeige.
STATUS_NORM: tuple[str, ...] = ("open", "started", "in_progress", "done", "paused", "unclear")

#: Woher eine Momentaufnahme stammt.
SOURCE_KINDS: tuple[str, ...] = ("template", "attachment", "klimaportal")

#: Rollen in ``council_plan_items``, die als Bericht zählen.
REPORT_ROLES: tuple[str, ...] = ("report", "evaluation")

#: Älter als das gilt ein Bericht nicht mehr als Stand; so lange hat ein neuer
#: Plan auch Zeit für den ersten. Derselbe Wert wie ``plan_pages.STALE_DAYS``.
STALE_DAYS = 730

#: Der Berichtsstand, in der Reihenfolge der Regel: Der erste Treffer gilt.
REPORT_STATES: tuple[tuple[str, str], ...] = (
    ("continued", "Fortgeschrieben"),
    ("in_preparation", "In Arbeit"),
    ("evaluated", "Ausgewertet"),
    ("expired_no_evaluation", "Laufzeit abgelaufen, keine Auswertung gefunden"),
    ("reported", "Berichtet"),
    ("not_yet_due", "Noch kein Bericht fällig"),
    ("no_report_found", "Kein Bericht gefunden"),
)
REPORT_STATE_LABELS = dict(REPORT_STATES)


# ── Daten ──────────────────────────────────────────────────────────────────


def period_start(iso: str) -> date:
    """``"2022"`` → 01.01.2022, ``"2022-12"`` → 01.12.2022, sonst der Tag selbst."""
    parts = [int(p) for p in iso.split("-")]
    return date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)


def period_end(iso: str) -> date:
    """``"2035"`` → 31.12.2035, ``"2031-06"`` → 30.06.2031 — eine Frist läuft bis zum Ende."""
    parts = [int(p) for p in iso.split("-")]
    if len(parts) > 2:
        return date(*parts[:3])
    month = parts[1] if len(parts) > 1 else 12
    return date(parts[0], month, calendar.monthrange(parts[0], month)[1])


def _months(a: date, b: date) -> int:
    """Volle Monate von ``a`` bis ``b`` (nie negativ)."""
    months = (b.year - a.year) * 12 + b.month - a.month - (1 if b.day < a.day else 0)
    return max(months, 0)


# ── 1. Berichtsstand ───────────────────────────────────────────────────────


def report_state(plan: register.Plan, items: list[dict], today: str) -> dict:
    """Wird über diesen Plan berichtet? Eine Aussage über den Bericht, nicht über die Arbeit.

    Die Reihenfolge ist die Regel (§ 3.3a): fortgeschrieben → in Arbeit →
    ausgewertet → abgelaufen ohne Auswertung → berichtet → noch nicht fällig →
    kein Bericht gefunden. Die eigene Überprüfungsfrist des Plans schlägt die
    zwei Jahre: Wer laut Plan erst 2031 überprüft wird, schuldet 2027 keinen
    Bericht.
    """
    now = date.fromisoformat(today)
    reports = [i for i in items if i["role"] in REPORT_ROLES]
    last = max((i["date"] for i in reports), default=None)
    evaluated = any(i["role"] == "evaluation" for i in reports)
    adopted = period_start(plan.adopted.date) if plan.adopted else None
    over = bool(plan.concluded) or (plan.end is not None and period_end(plan.end) < now)
    review = period_end(plan.review_due) if plan.review_due else None
    due = review if review and review > now else (adopted + timedelta(days=STALE_DAYS) if adopted else None)

    if plan.successor:
        state = "continued"
    elif adopted is None:
        state = "in_preparation"
    elif over and evaluated:
        state = "evaluated"
    elif over:
        state = "expired_no_evaluation"
    elif last and (now - date.fromisoformat(last)).days <= STALE_DAYS:
        state = "reported"
    elif last is None and due and due > now:
        state = "not_yet_due"
    else:
        state = "no_report_found"
    return {
        "state": state,
        "label": REPORT_STATE_LABELS[state],
        "last_report": last,
        # Bis wann der erste Bericht Zeit hat — nur solange er noch aussteht.
        "due": due.isoformat() if state == "not_yet_due" and due else None,
        "due_from_plan": bool(state == "not_yet_due" and review and review > now),
    }


# ── 2. Stand laut Stadt ────────────────────────────────────────────────────


@cache
def load(key: str) -> dict | None:
    """Die geprüfte Statusdatei eines Plans oder ``None``."""
    path = STATUS_DIR / f"{key}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def keys() -> list[str]:
    return sorted(p.stem for p in STATUS_DIR.glob("*.json")) if STATUS_DIR.exists() else []


def movement(before: dict, after: dict) -> dict:
    """Was sich zwischen zwei Momentaufnahmen bewegt hat, je Status im Wortlaut.

    Verglichen wird über ``status_raw``. Ändert die Stadt ein Wort, steht das
    alte mit ``count=0`` und das neue mit ``before=0`` da — das ist dann die
    ehrliche Auskunft, kein Fehler. Auch die Zählbasis kann sich bewegen
    (Klimaschutzplan 90 → 97); ``total_delta`` sagt es.
    """
    old = {c["status_raw"]: c["count"] for c in before["counts"]}
    rows = [{"status_raw": c["status_raw"], "status_norm": c["status_norm"], "count": c["count"],
             "before": old.get(c["status_raw"], 0), "delta": c["count"] - old.get(c["status_raw"], 0)}
            for c in after["counts"]]
    seen = {c["status_raw"] for c in after["counts"]}
    rows += [{"status_raw": c["status_raw"], "status_norm": c["status_norm"], "count": 0,
              "before": c["count"], "delta": -c["count"]}
             for c in before["counts"] if c["status_raw"] not in seen]
    return {"since": before["as_of"], "total_before": before["total"],
            "total_delta": after["total"] - before["total"], "counts": rows}


def city_status(key: str) -> dict | None:
    """Der jüngste Stand laut Stadt samt Bewegung seit dem vorigen und der ganzen Reihe."""
    data = load(key)
    if not data or not data.get("snapshots"):
        return None
    snapshots = sorted(data["snapshots"], key=lambda s: s["as_of"])
    latest = snapshots[-1]
    return {
        "latest": latest,
        "movement": movement(snapshots[-2], latest) if len(snapshots) > 1 else None,
        "series": [{"as_of": s["as_of"], "total": s["total"], "counts": s["counts"]} for s in snapshots],
        "notes": data.get("notes") or [],
    }


# ── 3. Eigene Termine ──────────────────────────────────────────────────────


def own_dates(plan: register.Plan, today: str) -> dict | None:
    """Was sich der Plan selbst vorgenommen hat: Laufzeit und Überprüfung, als Tatsachen.

    Gerechnet wird in vollen Monaten; ob daraus „knapp vier von dreizehn
    Jahren“ wird, entscheidet die Anzeige. Bewertet wird hier nichts — wer
    Termin und Stand nebeneinander sieht, zieht den Schluss selbst.
    """
    begin_iso = plan.start or (plan.adopted.date if plan.adopted else None)
    if begin_iso is None:
        return None
    now = date.fromisoformat(today)
    begin = period_start(begin_iso)
    end = period_end(plan.end) if plan.end else None
    review = period_end(plan.review_due) if plan.review_due else None
    return {
        "start": begin_iso,
        "end": plan.end,
        "elapsed_months": _months(begin, min(now, end) if end else now),
        "total_months": _months(begin, end) if end else None,
        "end_passed": bool(end and end < now),
        "review_due": plan.review_due,
        "review_passed": bool(review and review < now),
        "months_to_review": _months(now, review) if review and review >= now else None,
    }
