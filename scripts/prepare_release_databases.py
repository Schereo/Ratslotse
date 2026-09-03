#!/usr/bin/env python3
"""Create immutable release snapshots and apply forward-only migrations.

This is deliberately not a cron job.  The production workflow calls it only
after the API has stopped and the maintenance marker blocks newly started
Store users.  It drains older repo processes, locks both authoritative SQLite
databases against writes, creates verified non-rotating snapshots, and applies
all migrations explicitly before the regular services may start again.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from council.store import CouncilStore  # noqa: E402
from kern.maintenance import BYPASS_ENV, MARKER_NAME  # noqa: E402
from kern.store import Store  # noqa: E402
from scripts.verify_predeploy_backup import (  # noqa: E402
    DatabaseState,
    PreflightError,
    inspect_database,
    select_production_databases,
)
from scripts.verify_release_runtime import verify_quiescent  # noqa: E402


LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$")


class PreparationError(RuntimeError):
    """The release must stay inside the maintenance barrier."""


def _connect(path: Path, mode: str = "rw", timeout: float = 30) -> sqlite3.Connection:
    uri = f"file:{quote(str(path), safe='/')}?mode={mode}"
    return sqlite3.connect(uri, uri=True, timeout=timeout)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _same_manifest(source: DatabaseState, snapshot: DatabaseState) -> None:
    if source.schema_sha256 != snapshot.schema_sha256:
        raise PreparationError(
            f"Snapshot {snapshot.path.name} hat ein abweichendes Schema"
        )
    if source.table_rows != snapshot.table_rows:
        raise PreparationError(
            f"Snapshot {snapshot.path.name} hat ein abweichendes Tabellenmanifest"
        )


def _snapshot(
    source: DatabaseState, backup_dir: Path, label: str
) -> tuple[DatabaseState, dict]:
    destination = backup_dir / f"{source.path.stem}_predeploy_{label}.sqlite"
    temporary = backup_dir / f".{destination.name}.{os.getpid()}.tmp"
    if destination.exists() or temporary.exists():
        raise PreparationError(
            f"Release-Snapshot existiert bereits: {destination.name}"
        )

    source_connection = _connect(source.path, mode="ro")
    destination_connection: sqlite3.Connection | None = None
    try:
        destination_connection = sqlite3.connect(temporary)
        source_connection.backup(destination_connection)
        destination_connection.close()
        destination_connection = None
        temporary.replace(destination)
    except Exception:
        if destination_connection is not None:
            destination_connection.close()
        temporary.unlink(missing_ok=True)
        raise
    finally:
        source_connection.close()

    snapshot = inspect_database(destination, source.required_table)
    _same_manifest(source, snapshot)
    digest = _sha256(destination)
    return snapshot, {
        "source": source.path.name,
        "snapshot": destination.name,
        "bytes": destination.stat().st_size,
        "sha256": digest,
        "schema_sha256": snapshot.schema_sha256,
        "tables": dict(snapshot.table_rows),
    }


def _write_manifest(backup_dir: Path, label: str, databases: list[dict]) -> Path:
    path = backup_dir / f"predeploy_{label}.json"
    temporary = backup_dir / f".{path.name}.{os.getpid()}.tmp"
    if path.exists() or temporary.exists():
        raise PreparationError(f"Release-Manifest existiert bereits: {path.name}")
    document = {
        "format": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "databases": databases,
    }
    temporary.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def _lock_sources(states: list[DatabaseState]) -> list[sqlite3.Connection]:
    """Hold one write reservation per DB while separate readers back them up."""
    locks: list[sqlite3.Connection] = []
    try:
        for state in states:
            connection = _connect(state.path)
            try:
                connection.execute("PRAGMA busy_timeout=30000")
                connection.execute("BEGIN IMMEDIATE")
            except Exception:
                connection.close()
                raise
            locks.append(connection)
    except Exception:
        for connection in reversed(locks):
            connection.rollback()
            connection.close()
        raise
    return locks


def _release_locks(locks: list[sqlite3.Connection]) -> None:
    for connection in reversed(locks):
        connection.rollback()
        connection.close()


def open_database_handles(
    paths: list[Path],
    proc_root: Path = Path("/proc"),
    own_pid: int | None = None,
) -> list[tuple[int, str]]:
    """Find any process with a live DB/WAL/SHM descriptor, regardless of cwd."""
    own_pid = os.getpid() if own_pid is None else own_pid
    watched = {
        str(candidate)
        for path in paths
        for candidate in (
            path.resolve(),
            path.with_name(path.name + "-wal").resolve(),
            path.with_name(path.name + "-shm").resolve(),
        )
    }
    if not proc_root.is_dir():
        raise PreparationError("/proc fehlt; offene Datenbank-Handles sind nicht prüfbar")

    found: set[tuple[int, str]] = set()
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name) == own_pid:
            continue
        pid = int(entry.name)
        descriptor_dir = entry / "fd"
        try:
            descriptors = list(descriptor_dir.iterdir())
        except (OSError, PermissionError):
            continue
        for descriptor in descriptors:
            try:
                target = os.readlink(descriptor)
            except (OSError, PermissionError):
                continue
            target = target.removesuffix(" (deleted)")
            if target in watched:
                found.add((pid, Path(target).name))
    return sorted(found)


def prepare(root: Path, snapshot_label: str) -> tuple[Path, Path, Path]:
    """Snapshot both stores, migrate them, and verify their primary records."""
    root = root.resolve()
    marker = root / "data" / MARKER_NAME
    if not marker.is_file():
        raise PreparationError(f"Release-Wartungsmarker fehlt: {marker}")
    if os.environ.get(BYPASS_ENV) != "1":
        raise PreparationError(f"Explizite Freigabe über {BYPASS_ENV}=1 fehlt")
    if not LABEL_RE.fullmatch(snapshot_label):
        raise PreparationError("Snapshot-Label enthält unzulässige Zeichen")

    try:
        verify_quiescent(root)
        selection = select_production_databases(root)
    except PreflightError as error:
        raise PreparationError(str(error)) from error

    open_handles = open_database_handles(
        [selection.account.path, selection.council.path]
    )
    if open_handles:
        detail = ", ".join(f"PID {pid} ({name})" for pid, name in open_handles)
        raise PreparationError("Datenbankdateien sind noch geöffnet: " + detail)

    # Account first matches the ordering used by jobs that open both stores.
    # Re-inspect after both locks are held: this is the exact state represented
    # by the immutable snapshot and its manifest.
    locks = _lock_sources([selection.account, selection.council])
    backup_dir = root / "data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    try:
        account_source = inspect_database(
            selection.account.path, selection.account.required_table
        )
        council_source = inspect_database(
            selection.council.path, selection.council.required_table
        )
        account_snapshot, account_manifest = _snapshot(
            account_source, backup_dir, snapshot_label
        )
        council_snapshot, council_manifest = _snapshot(
            council_source, backup_dir, snapshot_label
        )
        manifest = _write_manifest(
            backup_dir,
            snapshot_label,
            [account_manifest, council_manifest],
        )
    finally:
        _release_locks(locks)

    # The marker still blocks every ordinary Store user. This process alone has
    # the explicit bypass and runs both migration stacks before service start.
    account = Store(selection.account_target)
    account.close()
    council = CouncilStore(
        selection.council.path,
        ratslotse_db_path=selection.account_target,
    )
    council.close()

    account_after = inspect_database(selection.account_target, "web_users")
    council_after = inspect_database(selection.council.path, "council_sessions")
    if account_after.rows != account_snapshot.rows:
        raise PreparationError("Kontenzahl hat sich während der Migration geändert")
    if council_after.rows != council_snapshot.rows:
        raise PreparationError("Sitzungszahl hat sich während der Migration geändert")

    print(
        "Release-Snapshots und Migrationen geprüft: "
        f"{account_snapshot.path.name}, {council_snapshot.path.name}; "
        f"Manifest {manifest.name}"
    )
    return selection.account_target, selection.council.path, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--snapshot-label", required=True)
    args = parser.parse_args()
    load_dotenv(args.root / ".env")
    try:
        prepare(args.root, args.snapshot_label)
    except PreparationError as error:
        parser.exit(1, f"RELEASE-MIGRATION BLOCKIERT: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
