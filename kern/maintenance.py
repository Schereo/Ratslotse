"""Fail-closed barrier around release-time database migrations.

The production deploy creates ``data/.release-maintenance`` before transferring
new code and keeps it through the build and database cutover. Any newly started
API or cron process must then refuse to open either SQLite database. Only the
dedicated preparation command receives the explicit bypass while it applies
the forward-only migrations against the verified final backup.
"""
from __future__ import annotations

import os
from pathlib import Path


MARKER_NAME = ".release-maintenance"
BYPASS_ENV = "RATSLOTSE_RELEASE_MAINTENANCE"


def marker_for_database(path: str | Path) -> Path | None:
    """Return the sibling maintenance marker, except for in-memory stores."""
    if str(path) == ":memory:":
        return None
    return Path(path).resolve().parent / MARKER_NAME


def require_database_available(path: str | Path) -> None:
    """Block ordinary database opens while the release cutover is active."""
    marker = marker_for_database(path)
    if (
        marker is not None
        and marker.exists()
        and os.environ.get(BYPASS_ENV) != "1"
    ):
        raise RuntimeError(
            f"Release-Wartung aktiv ({marker}); Datenbankzugriff bleibt gesperrt"
        )
