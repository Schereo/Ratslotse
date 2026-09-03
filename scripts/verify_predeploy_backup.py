#!/usr/bin/env python3
"""Fail-closed check of the database backup taken immediately before deploy.

The production deploy runs the *currently installed* ``backup_db.py`` before
``rsync`` replaces any code.  This verifier is streamed to the remote Python
interpreter from the checked-out release, so its checks are available even
though the release itself has not been copied to the server yet.

It deliberately prints no environment values.  Only database file names,
required table names and row counts appear in successful output or errors.
"""
from __future__ import annotations

import argparse
import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


class PreflightError(RuntimeError):
    """The deploy must stop before rsync or a service restart."""


@dataclass(frozen=True)
class DatabaseState:
    path: Path
    required_table: str
    rows: int
    table_rows: tuple[tuple[str, int], ...]
    schema_sha256: str


@dataclass(frozen=True)
class DatabaseSelection:
    council: DatabaseState
    account: DatabaseState
    account_target: Path


def _env_file(path: Path) -> dict[str, str]:
    """Read the small KEY=VALUE subset needed for database paths.

    This intentionally does not source the file and never returns or prints
    unrelated values such as API keys.
    """
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name not in {"COUNCIL_DB", "NWZ_DB", "RATSLOTSE_DB"}:
            continue
        values[name] = value.strip().strip("\"'")
    return values


def _resolve(root: Path, configured: str | None, default: Path) -> Path:
    path = Path(configured).expanduser() if configured else default
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _connect_read_only(path: Path) -> sqlite3.Connection:
    uri = f"file:{quote(str(path), safe='/')}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _quoted_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def inspect_database(path: Path, required_table: str) -> DatabaseState:
    """Require a non-empty, consistent SQLite DB with a populated key table."""
    if not path.is_file():
        raise PreflightError(f"Datenbank fehlt: {path.name}")
    if path.stat().st_size == 0:
        raise PreflightError(f"Datenbank ist leer: {path.name}")
    try:
        connection = _connect_read_only(path)
        try:
            quick_check = [row[0] for row in connection.execute("PRAGMA quick_check")]
            if quick_check != ["ok"]:
                detail = "; ".join(str(item) for item in quick_check[:3])
                raise PreflightError(
                    f"SQLite-Prüfung fehlgeschlagen für {path.name}: {detail}"
                )
            tables = [
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_schema "
                    "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                    "ORDER BY name"
                )
            ]
            if required_table not in tables:
                raise PreflightError(
                    f"{path.name} enthält die Pflichttabelle {required_table} nicht"
                )
            table_rows = tuple(
                (
                    table,
                    int(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {_quoted_identifier(table)}"
                        ).fetchone()[0]
                    ),
                )
                for table in tables
            )
            rows = dict(table_rows)[required_table]
            schema = "\n".join(
                "\0".join(str(value or "") for value in row)
                for row in connection.execute(
                    "SELECT type, name, tbl_name, sql FROM sqlite_schema "
                    "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
                )
            )
            schema_sha256 = hashlib.sha256(schema.encode()).hexdigest()
        finally:
            connection.close()
    except sqlite3.Error as error:
        raise PreflightError(
            f"{path.name} ist keine lesbare SQLite-Datenbank: {error}"
        ) from error
    if rows <= 0:
        raise PreflightError(
            f"{path.name}.{required_table} enthält keine Zeilen"
        )
    return DatabaseState(
        path=path,
        required_table=required_table,
        rows=rows,
        table_rows=table_rows,
        schema_sha256=schema_sha256,
    )


def _inside_data_dir(path: Path, data_dir: Path) -> None:
    """The installed backup job only covers direct ``data/*.sqlite`` files."""
    if path.parent != data_dir:
        raise PreflightError(
            f"{path.name} liegt nicht direkt unter data/ und wird von "
            "scripts/backup_db.py nicht erfasst"
        )


def _fresh_backup(source: DatabaseState, backup_dir: Path, marker: Path) -> DatabaseState:
    if not marker.is_file():
        raise PreflightError("Startmarke des Pre-Deploy-Backups fehlt")
    candidates = sorted(
        backup_dir.glob(f"{source.path.stem}_*.sqlite"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    if not candidates:
        raise PreflightError(f"Kein Backup für {source.path.name} gefunden")
    backup = candidates[0]
    if backup.stat().st_mtime_ns <= marker.stat().st_mtime_ns:
        raise PreflightError(
            f"Backup für {source.path.name} wurde nicht in diesem Deploy-Lauf erzeugt"
        )
    state = inspect_database(backup, source.required_table)
    if state.schema_sha256 != source.schema_sha256:
        raise PreflightError(
            f"Backup für {source.path.name} hat nicht dasselbe Schema wie die Quelle"
        )
    if state.table_rows != source.table_rows:
        raise PreflightError(
            f"Backup für {source.path.name} hat ein abweichendes Tabellenmanifest"
        )
    return state


def select_production_databases(root: Path) -> DatabaseSelection:
    """Resolve and validate the two authoritative production databases."""
    root = root.resolve()
    data_dir = (root / "data").resolve()
    values = _env_file(root / ".env")

    council_path = _resolve(
        root, values.get("COUNCIL_DB"), data_dir / "council.sqlite"
    )
    _inside_data_dir(council_path, data_dir)
    council = inspect_database(council_path, "council_sessions")

    future_account = _resolve(
        root, values.get("RATSLOTSE_DB"), data_dir / "ratslotse.sqlite"
    )
    old_account = _resolve(
        root, values.get("NWZ_DB"), future_account.with_name("nwz.sqlite")
    )
    account_paths = list(dict.fromkeys((future_account, old_account)))
    for path in account_paths:
        _inside_data_dir(path, data_dir)

    populated: list[DatabaseState] = []
    for path in account_paths:
        if not path.is_file() or path.stat().st_size == 0:
            continue
        state = inspect_database(path, "web_users")
        populated.append(state)

    if not populated:
        raise PreflightError(
            "Weder ratslotse.sqlite noch nwz.sqlite enthält einen befüllten Account-Bestand"
        )
    if len(populated) > 1:
        names = ", ".join(state.path.name for state in populated)
        raise PreflightError(
            f"Mehrere Account-Datenbanken sind befüllt ({names}); "
            "der Deploy kann den maßgeblichen Bestand nicht sicher bestimmen"
        )
    account = populated[0]

    # The release migrates the old sibling only if the new target is absent or
    # exactly zero bytes.  A schema-initialized but empty target would suppress
    # that migration and start production without the existing accounts.
    if account.path == old_account:
        if future_account.name != "ratslotse.sqlite":
            raise PreflightError(
                "RATSLOTSE_DB muss für den automatischen Umzug auf eine Datei "
                "namens ratslotse.sqlite zeigen"
            )
    if account.path == old_account and future_account != old_account:
        if future_account.exists() and future_account.stat().st_size > 0:
            raise PreflightError(
                f"{future_account.name} ist nicht leer und blockiert den Umzug von "
                f"{old_account.name}"
            )
        expected_old = future_account.with_name("nwz.sqlite")
        if old_account != expected_old:
            raise PreflightError(
                "NWZ_DB zeigt nicht auf die Datei, die der neue Store automatisch "
                "nach RATSLOTSE_DB migriert"
            )

    return DatabaseSelection(
        council=council,
        account=account,
        account_target=future_account,
    )


def verify(root: Path, marker: Path) -> tuple[DatabaseState, DatabaseState]:
    root = root.resolve()
    selection = select_production_databases(root)
    council = selection.council
    account = selection.account
    backup_dir = root / "data" / "backups"

    council_backup = _fresh_backup(council, backup_dir, marker)
    account_backup = _fresh_backup(account, backup_dir, marker)
    print(
        f"Pre-Deploy-Backup geprüft: {council.path.name} "
        f"({council.rows} Sitzungen) → {council_backup.path.name}; "
        f"{account.path.name} ({account.rows} Konten) → {account_backup.path.name}"
    )
    return council, account


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--newer-than", type=Path, required=True)
    args = parser.parse_args()
    try:
        verify(args.root, args.newer_than)
    except PreflightError as error:
        parser.exit(1, f"PRE-DEPLOY BLOCKIERT: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
