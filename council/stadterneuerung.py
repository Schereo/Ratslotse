"""Stadterneuerungsgebiete — für die Tafel eines Ortsbereichs.

Die Stadt führt ihre sechs Gebiete der Städtebauförderung im Geoportal (Ebene „Bauen und Wohnen –
Stadterneuerungsgebiete“) mit Umriss, Laufzeit, Fördermitteln und Eigenmitteln. Eingelesen
von ``scripts/stadterneuerung.py`` nach ``council/stadterneuerung.json`` (eingecheckt); welche
Ortsbereiche ein Gebiet berührt, ist dort mitgerechnet.
"""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path

FILE = Path(__file__).resolve().parent / "stadterneuerung.json"
#: Ab diesem Anteil seiner Fläche gehört ein Gebiet zu einem Ortsbereich.
AREA_SHARE = 0.1
SOURCE_LABEL = "Geoportal der Stadt Oldenburg, Ebene „Stadterneuerungsgebiete“"


@cache
def data() -> dict:
    if not FILE.exists():
        return {"areas": []}
    return json.loads(FILE.read_text(encoding="utf-8"))


def for_district(place_id: str) -> list[dict]:
    """Die Gebiete, von deren Fläche mindestens ``AREA_SHARE`` in diesem Ortsbereich liegt."""
    out = []
    for area in data()["areas"]:
        if area["districts"].get(place_id, 0) < AREA_SHARE:
            continue
        out.append({"name": area["name"], "start_year": area["start_year"], "end_year": area["end_year"],
                    "size_ha": area["size_ha"], "funding_eur": area["funding_eur"],
                    "own_funds_eur": area["own_funds_eur"], "source": SOURCE_LABEL})
    out.sort(key=lambda a: (-a["end_year"], a["name"]))
    return out
