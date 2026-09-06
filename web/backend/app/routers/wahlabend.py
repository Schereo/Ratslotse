"""Wahlabend zur Ratswahl 13.09.2026 — ``GET /api/wahlabend``.

Öffentlich (die Zahlen sind es auch: Open Data der Stadt), aber hinter dem
Feature-Schalter ``wahlabend``: Ohne ihn antwortet der Endpunkt 404, damit die
Seite bis zum Wahlabend dunkel bleiben kann und danach ohne Deploy wieder.

``?probe=2021`` liefert die Generalprobe (Zahlen von 2021 im Register von
2026), ``&counted=N`` davon nur die ersten N Wahlbezirke ausgezählt.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from kern import features

from ..antworten import ElectionNight
from ..election import service

router = APIRouter(tags=["wahlabend"])


@router.get("/api/wahlabend")
def wahlabend(
    probe: str | None = Query(default=None, description="„2021“ = Generalprobe mit den Zahlen von 2021"),
    counted: int | None = Query(default=None, ge=0, le=500, description="Generalprobe: nur die ersten N Wahlbezirke ausgezählt"),
) -> ElectionNight:
    if not features.an("wahlabend"):
        raise HTTPException(status_code=404, detail="Der Wahlabend ist noch nicht freigeschaltet.")
    if probe == "2021":
        return service.probe(counted)
    return service.live()
