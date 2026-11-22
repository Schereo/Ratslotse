"""Werkzeuge für die Ratsarbeit — nur mit dem Recht ``council_tools``.

Ein eigener Bereich, den nur Ratsmitglieder (und Admins) sehen (Tims Wunsch
22.11.2026). Erstes Werkzeug: der Mehrheitsrechner über Rat, Verwaltungs-
ausschuss und Fachausschüsse; gerechnet wird in ``app/majorities.py``.

**Die Sperre sitzt hier**, nicht im Browser: Jede Route unter
``/api/tools`` verlangt das Recht, und ``tests/test_werkzeuge.py`` hält das
für jede künftige Route fest.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from council.store import CouncilStore

from .. import majorities
from ..antworten import MajorityCalculator
from ..deps import get_council_store, require_permission

router = APIRouter(prefix="/api/tools", tags=["tools"])
require_tools = require_permission("council_tools")


def _keys(raw: str | None) -> list[str]:
    return [k.strip() for k in (raw or "").split(",") if k.strip()][:30]


@router.get("/majorities")
def majority_calculator(
    body: str | None = Query(None, max_length=120, description="Gremium (Schlüssel aus `bodies`); "
                             "ohne Angabe der Rat."),
    include: str | None = Query(None, max_length=400,
                                description="Kommagetrennte Blöcke, die dabei sein sollen."),
    exclude: str | None = Query(None, max_length=400,
                                description="Kommagetrennte Blöcke, die nicht dabei sein sollen."),
    _user: dict = Depends(require_tools),
    store: CouncilStore = Depends(get_council_store),
) -> MajorityCalculator:
    """Sitze je Fraktion, Mehrheitsschwelle und jede Kombination, die mit der
    Auswahl eine Mehrheit ergibt."""
    return majorities.calculate(store.committee_seats(), body, _keys(include), _keys(exclude))
