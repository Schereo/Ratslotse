"""Fiktive Projektionen ausschließlich für die isolierte Feature-Instanz."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from .store import ProblemStore

_PUBLISHED_AT = "2026-09-02T12:00:00+00:00"

# Alle Beispiele sind erfunden. Ortsbezeichnungen vermeiden reale Adressen;
# die Koordinaten dienen nur dazu, die Geometrieformen in Oldenburg zu prüfen.
_EXAMPLES: tuple[dict[str, Any], ...] = (
    {
        "key": "issue-1034-point",
        "title": "Beispiel: dunkler Fußweg am Musterkanal",
        "summary": "Fiktive Zusammenfassung einer fehlenden Beleuchtung.",
        "category": "public_space",
        "scope_kind": "point",
        "location_label": "Fiktiver Beispielort",
        "latitude": 53.1399,
        "longitude": 8.2148,
        "status": "multiple_reports",
        "reports": 3,
    },
    {
        "key": "issue-1034-facility",
        "title": "Beispiel: Fahrradständer an der Musterhalle überfüllt",
        "summary": "Fiktive Zusammenfassung zu einer erfundenen Einrichtung.",
        "category": "mobility",
        "scope_kind": "facility",
        "location_label": "Fiktive Musterhalle",
        "latitude": 53.1434,
        "longitude": 8.2227,
        "status": "verified",
        "reports": 11,
    },
    {
        "key": "issue-1034-route",
        "title": "Beispiel: Lücke auf einer fiktiven Radroute",
        "summary": "Fiktiver Streckenabschnitt für die Routendarstellung.",
        "category": "mobility",
        "scope_kind": "route",
        "location_label": "Fiktive Beispielroute",
        "geometry": {
            "type": "LineString",
            "coordinates": [[8.197, 53.142], [8.204, 53.143], [8.219, 53.144]],
        },
        "status": "new",
        "reports": 1,
    },
    {
        "key": "issue-1034-polygon",
        "title": "Beispiel: wenig Schatten im Musterquartier",
        "summary": "Fiktive Fläche für die Polygondarstellung.",
        "category": "environment",
        "scope_kind": "area",
        "location_label": "Fiktives Musterquartier",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [8.205, 53.135], [8.217, 53.135], [8.22, 53.142],
                [8.208, 53.144], [8.205, 53.135],
            ]],
        },
        "status": "persists",
        "reports": 7,
    },
    {
        "key": "issue-1034-multipolygon",
        "title": "Beispiel: zwei fiktive Grünflächen ohne Zugang",
        "summary": "Fiktive getrennte Flächen für die MultiPolygon-Darstellung.",
        "category": "accessibility",
        "scope_kind": "area",
        "location_label": "Zwei fiktive Teilgebiete",
        "geometry": {
            "type": "MultiPolygon",
            "coordinates": [
                [[[8.18, 53.13], [8.185, 53.13], [8.185, 53.134], [8.18, 53.13]]],
                [[[8.225, 53.15], [8.23, 53.15], [8.23, 53.154], [8.225, 53.15]]],
            ],
        },
        "status": "verified",
        "reports": 5,
    },
    {
        "key": "issue-1034-citywide",
        "title": "Beispiel: fiktiver stadtweiter Betreuungsengpass",
        "summary": "Fiktives stadtweites Problem ohne erfundenen Kartenpunkt.",
        "category": "childcare",
        "scope_kind": "citywide",
        "location_label": "Gesamtes Stadtgebiet (Beispiel)",
        "status": "multiple_reports",
        "reports": 18,
    },
    {
        "key": "issue-1034-malformed",
        "title": "Beispiel: ältere Route ohne brauchbare Geometrie",
        "summary": "Fiktiver Altbestand, der nur im vollständigen Board stehen darf.",
        "category": "mobility",
        "scope_kind": "route",
        "location_label": "Fiktiver Altbestand",
        "geometry": {"type": "LineString", "coordinates": [[8.2, 53.14]]},
        "status": "apparently_resolved",
        "reports": 2,
    },
)


def _guard_feature_database(database: Path, deployment_root: Path) -> None:
    """Stop before opening a DB unless this is exactly ``app-feature/data``."""
    root = deployment_root.expanduser().resolve()
    target = database.expanduser().resolve()
    expected = (root / "data" / "ratslotse.sqlite").resolve()
    if os.environ.get("RATSLOTSE_FEATURE_SEED") != "1":
        raise RuntimeError("Feature-Beispiele sind nicht ausdrücklich freigeschaltet.")
    if root.name != "app-feature" or target != expected:
        raise RuntimeError(
            "Feature-Beispiele dürfen nur app-feature/data/ratslotse.sqlite verändern."
        )


def seed_feature_examples(
    database: str | Path,
    *,
    deployment_root: str | Path,
) -> int:
    """Upsert the fixed fictional set after the feature-only path guard."""
    database_path = Path(database)
    root = Path(deployment_root)
    _guard_feature_database(database_path, root)

    # Erst nach bestandenem Guard werden Verzeichnisse oder Datenbank angefasst.
    ProblemStore(database_path).close()
    connection = sqlite3.connect(database_path)
    try:
        with connection:
            for example in _EXAMPLES:
                connection.execute(
                    """INSERT INTO civic_problems (
                           example_key, title, summary, category, tags_json,
                           scope_kind, location_label, latitude, longitude,
                           geometry_json, status, independent_reports,
                           first_observed_at, last_observed_at, published_at,
                           updated_at, is_fictional
                       ) VALUES (?, ?, ?, ?, '[]', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                       ON CONFLICT(example_key) DO UPDATE SET
                           title = excluded.title,
                           summary = excluded.summary,
                           category = excluded.category,
                           scope_kind = excluded.scope_kind,
                           location_label = excluded.location_label,
                           latitude = excluded.latitude,
                           longitude = excluded.longitude,
                           geometry_json = excluded.geometry_json,
                           status = excluded.status,
                           independent_reports = excluded.independent_reports,
                           first_observed_at = excluded.first_observed_at,
                           last_observed_at = excluded.last_observed_at,
                           published_at = excluded.published_at,
                           updated_at = excluded.updated_at,
                           is_fictional = 1""",
                    (
                        example["key"],
                        example["title"],
                        example["summary"],
                        example["category"],
                        example["scope_kind"],
                        example["location_label"],
                        example.get("latitude"),
                        example.get("longitude"),
                        json.dumps(example.get("geometry"), ensure_ascii=False)
                        if example.get("geometry") else None,
                        example["status"],
                        example["reports"],
                        _PUBLISHED_AT,
                        _PUBLISHED_AT,
                        _PUBLISHED_AT,
                        _PUBLISHED_AT,
                    ),
                )
    finally:
        connection.close()
    return len(_EXAMPLES)
