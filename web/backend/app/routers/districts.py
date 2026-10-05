"""„Mein Viertel": Vorhaben je Ortsbereich — was sich dort in den nächsten Jahren ändert.

**Nur mit Konto.** Alle Endpunkte hier verlangen ein aktives Konto, wie die
Stadtkarte selbst (Tims Entscheidung 07.09.2026: öffentlich bleibt nur die
Landingpage). Ein geteilter Tafel-Link führt Empfänger*innen ohne Konto also
auf die Anmeldung und nach ihr zurück auf die Tafel — eine öffentliche Ansicht
gibt es nicht, und der Teilen-Knopf sagt das dazu.

Das Register selbst rechnet ``scripts/build_district_projects.py`` (wöchentlich
in ``weekly_enrich``); hier wird nur gelesen — plus „Gehört nicht hierher"
(melden, zurücknehmen) und die Admin-Liste dieser Meldungen.
"""
from __future__ import annotations

import html
from typing import Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from council import geo
from council.store import CouncilStore

from ..antworten import (
    AdminDistrictReports,
    DistrictLookup,
    DistrictLookupMatch,
    DistrictProjectReportOut,
    DistrictProjects,
    DistrictProjectsOverview,
    Ok,
)
from ..deps import get_council_store, require_active, require_admin
from ..ratelimit import district_report_limiter

router = APIRouter(prefix="/api/districts", tags=["districts"])


class ProjectReportIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


def _primary_places(store: CouncilStore) -> list:
    return [p for p in store.all_places() if p.is_primary]


# Seit dem Umzug auf die vereinte Stadtkarte (STADTKARTE-PLAN.md, Schritt 5)
# verlangen alle drei Lese-Endpunkte ein Konto — wie die Karte selbst (Tims
# Entscheidung 07.09.2026: öffentlich bleibt nur die Landingpage). Vorher waren
# Übersicht und Suche offen, damit ein geteilter Tafel-Link ohne Konto ging.
@router.get("/projects")
def district_projects_overview(
    _user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> DistrictProjectsOverview:
    """Alle Ortsbereiche mit der Zahl ihrer Vorhaben — für die Auswahl-Seite.

    Dazu die Stadtzahlen (wie viele Vorhaben, wie viele je Stand) und die
    Vorhaben, die gerade herausstechen: Die Seite ohne gewähltes Viertel soll
    schon etwas zeigen, nicht nur fragen."""
    overview = store.district_projects_overview()
    rows = []
    updated: str | None = None
    for place in sorted(_primary_places(store), key=lambda p: p.name):
        o = overview.get(place.id) or {}
        rows.append({"place_id": place.id, "name": place.name, "count": o.get("count", 0),
                     "last_date": o.get("last_date"), "stages": o.get("stages") or {}})
        if o.get("updated_at") and (updated is None or o["updated_at"] > updated):
            updated = o["updated_at"]
    # Die Stadtzahl ist NICHT die Summe der Viertel: Ein Vorhaben an der
    # Grenze steht auf zwei Tafeln, zählt in der Stadt aber einmal.
    stadt = store.district_city_totals()
    # Lose dicts aus dem Store; die Form hält der Vertrag, geprüft vom Test.
    return cast(DistrictProjectsOverview, {
        "districts": rows, "total": stadt["total"], "stages": stadt["stages"],
        "shared": stadt["shared"],
        "highlights": store.district_highlights(), "updated_at": updated,
        "decisions_until": store.district_decisions_until(),
    })


@router.get("/lookup")
def district_lookup(q: str = Query("", max_length=80),
                    _user: dict = Depends(require_active),
                    store: CouncilStore = Depends(get_council_store)) -> DistrictLookup:
    """„Ich wohne in der …": Straße, Platz oder Stadtteilname → Ortsbereich.

    Stadtteile (Name und Aliase) zuerst, dann Straßen und Plätze aus den
    Beschlüssen. Mit Konto wie die Auswahl-Seite selbst; kein Sprachmodell,
    keine Speicherung der Eingabe."""
    q = q.strip()
    if len(q) < 2:
        return {"matches": []}
    overview = store.district_projects_overview()
    needle = q.lower()
    matches: list[DistrictLookupMatch] = []
    for place in sorted(_primary_places(store), key=lambda p: p.name):
        if any(n.lower().startswith(needle) for n in (place.name, *place.aliases)):
            matches.append({"name": place.name, "kind": "district", "place_id": place.id,
                            "place_name": place.name,
                            "count": (overview.get(place.id) or {}).get("count", 0)})
    for m in store.district_lookup_streets(q, limit=6):
        matches.append({"name": m["name"], "kind": m["kind"], "place_id": m["place_id"],
                        "place_name": m["place_name"],
                        "count": (overview.get(m["place_id"]) or {}).get("count", 0)})
    return {"matches": matches[:8]}


@router.get("/{place_id}/projects")
def district_projects(
    place_id: str,
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> DistrictProjects:
    """Die Tafel eines Ortsbereichs: Vorhaben mit Stand, dazu was demnächst im
    Rat ansteht, was im Investitionsprogramm steht, wo gerade eine
    Beteiligung läuft, was die Stadt gesperrt hat und was sie zum Viertel
    mitgeteilt hat."""
    place = store.resolve_place(place_id)
    if not place or not place.is_primary:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ortsbereich nicht gefunden.")
    reported = store.district_project_reports_by(user["id"], place.id) if user else set()
    projects = []
    for p in store.district_projects(place.id):
        projects.append({**p, "reported": p["project_key"] in reported})
    overview = store.district_projects_overview()
    by_name = {p.name: p for p in _primary_places(store)}
    neighbours = []
    for name in geo.nachbar_ortsbereiche(place.name):
        nb = by_name.get(name)
        if nb:
            neighbours.append({"place_id": nb.id, "name": nb.name,
                               "count": (overview.get(nb.id) or {}).get("count", 0)})
    # Der Store liefert lose dicts; die Form hält der Vertrag (antworten.py),
    # geprüft von der Rauchprobe — hier nur die Zusage an den Typprüfer.
    return cast(DistrictProjects, {
        "place": store.public_place(place),
        "projects": projects,
        "upcoming": store.district_upcoming_items(place),
        "investments": store.district_investments(place),
        "participations": store.district_participations(place),
        "closures": store.district_road_closures(place.id),
        "press": store.district_press(place.id),
        "neighbours": neighbours,
        "updated_at": store.district_projects_updated_at(place.id),
        "decisions_until": store.district_decisions_until(),
    })


def _melde_redaktion(project: dict, place_name: str, reason: str | None) -> None:
    """Die erste Meldung zu einem Vorhaben geht als Mail an ``ALERT_EMAIL``
    (Rückfall ``WEB_ADMIN_EMAIL``) — über den Betriebsweg, nicht über
    ``notify.einreihen``: Das ist eine Nachricht an die Redaktion, keine
    Benachrichtigung einer Nutzerin. Weitere Meldungen zählt nur die Liste."""
    from kern.alerts import notify_admin
    from kern.digest_email import APP_BASE_URL

    grund = html.escape(reason) if reason else "<i>kein Grund angegeben</i>"
    notify_admin(
        f"<b>{html.escape(project['name'])}</b> ({html.escape(place_name)}) wurde als "
        f"„Gehört nicht hierher“ gemeldet.\n\nGrund: {grund}\n\n"
        f"Das Vorhaben bleibt sichtbar, bis jemand entscheidet: {APP_BASE_URL}/admin#viertel",
        betreff="Ratslotse – Meldung zu Mein Viertel",
        fusszeile="Nur die erste Meldung je Vorhaben kommt als Mail — weitere stehen in der Admin-Liste.",
    )


@router.post("/projects/{project_id}/report", status_code=status.HTTP_201_CREATED)
def report_project(
    project_id: int,
    body: ProjectReportIn,
    request: Request,
    background: BackgroundTasks,
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> DistrictProjectReportOut:
    """„Gehört nicht hierher": Ein Konto meldet ein Vorhaben als falsch verortet.

    **Eine Meldung blendet nichts aus.** Bis 10/2026 verschwand ein Vorhaben ab
    zwei Meldungen dauerhaft — zwei Konten konnten so jede Tafel leeren, und
    niemand sah die Meldungen. Jetzt landet sie in der Admin-Liste, die erste
    je Vorhaben zusätzlich als Mail, und ausgeblendet wird erst, wenn die
    Redaktion bestätigt. Die Meldung hängt am Konto und geht mit dessen
    Löschung (``COUNCIL_USER_OWNED_TABLES``)."""
    district_report_limiter.check(request, subject=user["id"])
    project = store.district_project_by_id(project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vorhaben nicht gefunden.")
    neu = store.save_district_project_report(project["project_key"], project["place_id"], user["id"],
                                             body.reason, project["name"])
    count = store.district_project_report_count(project["project_key"])
    if neu and count == 1:
        place = store.resolve_place(project["place_id"])
        background.add_task(_melde_redaktion, project, place.name if place else project["place_id"],
                            (body.reason or "").strip() or None)
    return {"ok": True, "report_count": count, "hidden": store.district_project_hidden(project["project_key"]),
            "reported": True}


@router.delete("/projects/{project_id}/report")
def withdraw_project_report(
    project_id: int,
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> DistrictProjectReportOut:
    """Die eigene Meldung zurücknehmen — ein Fehltipp soll nicht stehen bleiben.
    Eine Entscheidung der Redaktion bleibt davon unberührt."""
    project = store.district_project_by_id(project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vorhaben nicht gefunden.")
    store.delete_district_project_report(project["project_key"], user["id"])
    count = store.district_project_report_count(project["project_key"])
    return {"ok": True, "report_count": count, "hidden": store.district_project_hidden(project["project_key"]),
            "reported": False}


# ---------------------------------------------------------------- Admin

admin_router = APIRouter(prefix="/api/admin/district-reports", tags=["admin"])


class VerdictIn(BaseModel):
    #: ``hidden`` blendet aus, ``kept`` lässt stehen, ``None`` macht die
    #: Meldungen wieder offen.
    verdict: Literal["hidden", "kept"] | None
    note: str | None = Field(default=None, max_length=300)


@admin_router.get("")
def district_reports(
    review_status: str = Query("open", alias="status", pattern="^(open|decided|all)$"),
    _admin: dict = Depends(require_admin),
    store: CouncilStore = Depends(get_council_store),
) -> AdminDistrictReports:
    """Die Meldungen aus „Mein Viertel", je Vorhaben gebündelt."""
    alle = store.district_report_groups("all")
    gruppen = [g for g in alle if review_status == "all" or (review_status == "open") == (g["verdict"] is None)]
    return cast(AdminDistrictReports, {
        "groups": gruppen, "status": review_status,
        "open_count": sum(1 for g in alle if g["verdict"] is None),
    })


@admin_router.put("/{project_key}")
def decide_district_report(
    project_key: str,
    body: VerdictIn,
    _admin: dict = Depends(require_admin),
    store: CouncilStore = Depends(get_council_store),
) -> Ok:
    """Entscheiden: ausblenden, stehen lassen — oder die Entscheidung zurücknehmen."""
    if not store.set_district_project_verdict(project_key, body.verdict, body.note) and body.verdict:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zu diesem Vorhaben gibt es keine Meldung.")
    return {"ok": True}
