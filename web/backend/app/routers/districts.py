"""„Mein Viertel": Vorhaben je Ortsbereich — was sich dort in den nächsten Jahren ändert.

Öffentlich lesbar wie Beschluss- und Ortsseiten: Die Tafel eines Viertels
ist der Link, den man der Nachbarin schickt, und die soll ihn ohne Konto
öffnen können. Angemeldete bekommen auf derselben Seite den Zusatz, welche
Vorhaben sie schon gemeldet haben.

Das Register selbst rechnet ``scripts/build_district_projects.py`` (wöchentlich
in ``weekly_enrich``); hier wird nur gelesen — plus die eine Schreibhandlung
„Gehört nicht hierher".
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from council import geo
from council.store import CouncilStore

from ..antworten import (
    DistrictProjectReportOut,
    DistrictProjects,
    DistrictProjectsOverview,
)
from ..deps import get_council_store, optional_user, require_active

router = APIRouter(prefix="/api/districts", tags=["districts"])


class ProjectReportIn(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


def _primary_places(store: CouncilStore) -> list:
    return [p for p in store.all_places() if p.is_primary]


@router.get("/projects")
def district_projects_overview(store: CouncilStore = Depends(get_council_store)) -> DistrictProjectsOverview:
    """Alle Ortsbereiche mit der Zahl ihrer Vorhaben — für die Auswahl-Seite."""
    overview = store.district_projects_overview()
    rows = []
    updated: str | None = None
    for place in sorted(_primary_places(store), key=lambda p: p.name):
        o = overview.get(place.id) or {}
        rows.append({"place_id": place.id, "name": place.name, "count": o.get("count", 0),
                     "last_date": o.get("last_date")})
        if o.get("updated_at") and (updated is None or o["updated_at"] > updated):
            updated = o["updated_at"]
    return {"districts": rows, "updated_at": updated}


@router.get("/{place_id}/projects")
def district_projects(
    place_id: str,
    user: dict | None = Depends(optional_user),
    store: CouncilStore = Depends(get_council_store),
) -> DistrictProjects:
    """Die Tafel eines Ortsbereichs: Vorhaben mit Stand, dazu was demnächst im
    Rat ansteht, was im Investitionsprogramm steht und wo gerade eine
    Beteiligung läuft."""
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
    return {
        "place": store.public_place(place),
        "projects": projects,
        "upcoming": store.district_upcoming_items(place),
        "investments": store.district_investments(place),
        "participations": store.district_participations(place),
        "neighbours": neighbours,
        "updated_at": store.district_projects_updated_at(place.id),
    }


@router.post("/projects/{project_id}/report", status_code=status.HTTP_201_CREATED)
def report_project(
    project_id: int,
    body: ProjectReportIn,
    user: dict = Depends(require_active),
    store: CouncilStore = Depends(get_council_store),
) -> DistrictProjectReportOut:
    """„Gehört nicht hierher": Ein Konto meldet ein Vorhaben als falsch verortet.
    Ab zwei Meldungen verschwindet es von der Tafel; die Meldung bleibt beim
    Konto und geht mit dessen Löschung."""
    project = store.district_project_by_id(project_id)
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vorhaben nicht gefunden.")
    store.save_district_project_report(project["project_key"], project["place_id"], user["id"], body.reason)
    count = store.district_project_report_count(project["project_key"])
    from council.store_viertel import PROJECT_HIDE_REPORTS
    return {"ok": True, "report_count": count, "hidden": count >= PROJECT_HIDE_REPORTS}
