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

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from council import geo
from council.store import CouncilStore

from ..antworten import (
    DistrictLookup,
    DistrictLookupMatch,
    DistrictProjectReportOut,
    DistrictProjects,
    DistrictProjectsOverview,
)
from ..deps import get_council_store, require_active

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
    stages: dict[str, int] = {}
    for place in sorted(_primary_places(store), key=lambda p: p.name):
        o = overview.get(place.id) or {}
        rows.append({"place_id": place.id, "name": place.name, "count": o.get("count", 0),
                     "last_date": o.get("last_date"), "stages": o.get("stages") or {}})
        for stage, n in (o.get("stages") or {}).items():
            stages[stage] = stages.get(stage, 0) + n
        if o.get("updated_at") and (updated is None or o["updated_at"] > updated):
            updated = o["updated_at"]
    # Lose dicts aus dem Store; die Form hält der Vertrag, geprüft vom Test.
    return cast(DistrictProjectsOverview, {
        "districts": rows, "total": sum(r["count"] for r in rows), "stages": stages,
        "highlights": store.district_highlights(), "updated_at": updated,
    })


@router.get("/lookup")
def district_lookup(q: str = Query("", max_length=80),
                    _user: dict = Depends(require_active),
                    store: CouncilStore = Depends(get_council_store)) -> DistrictLookup:
    """„Ich wohne in der …": Straße, Platz oder Stadtteilname → Ortsbereich.

    Stadtteile (Name und Aliase) zuerst, dann Straßen und Plätze aus den
    Beschlüssen. Öffentlich wie die Auswahl-Seite selbst; kein Konto, kein
    Sprachmodell, keine Speicherung der Eingabe."""
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
    })


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
