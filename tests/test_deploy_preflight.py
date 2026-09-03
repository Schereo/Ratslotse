"""Der Produktions-Deploy darf ohne frisches, eindeutiges Backup nicht starten."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from council.store import CouncilStore  # noqa: E402
from council.scraper import CouncilSession  # noqa: E402
from kern.maintenance import BYPASS_ENV, MARKER_NAME  # noqa: E402
from kern.store import Store  # noqa: E402
from scripts import prepare_release_databases  # noqa: E402
from scripts.verify_predeploy_backup import PreflightError, verify  # noqa: E402
from scripts.verify_release_runtime import (  # noqa: E402
    PreflightError as RuntimePreflightError,
    running_repo_python_processes,
    verify_configuration,
    verify_crontab,
    verify_systemd_permissions,
)


def _database(path: Path, table: str, rows: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(f'CREATE TABLE "{table}" (id INTEGER PRIMARY KEY)')
    connection.executemany(
        f'INSERT INTO "{table}" (id) VALUES (?)', ((i + 1,) for i in range(rows))
    )
    connection.commit()
    connection.close()


def _setup(root: Path, account_name: str = "nwz.sqlite") -> Path:
    data = root / "data"
    backup = data / "backups"
    _database(data / "council.sqlite", "council_sessions", rows=3)
    _database(data / account_name, "web_users", rows=2)
    _database(backup / "council_2026-09-03.sqlite", "council_sessions", rows=3)
    _database(backup / f"{Path(account_name).stem}_2026-09-03.sqlite", "web_users", rows=2)
    marker = backup / ".predeploy-start"
    marker.touch()
    for path in backup.glob("*.sqlite"):
        os.utime(path, ns=(marker.stat().st_mtime_ns + 1, marker.stat().st_mtime_ns + 1))
    return marker


def test_preflight_accepts_fresh_council_and_old_account_backup(tmp_path):
    marker = _setup(tmp_path)

    council, account = verify(tmp_path, marker)

    assert council.path.name == "council.sqlite"
    assert council.rows == 3
    assert account.path.name == "nwz.sqlite"
    assert account.rows == 2


def test_preflight_rejects_two_populated_account_databases(tmp_path):
    marker = _setup(tmp_path)
    _database(tmp_path / "data" / "ratslotse.sqlite", "web_users", rows=1)

    with pytest.raises(PreflightError, match="Mehrere Account-Datenbanken"):
        verify(tmp_path, marker)


def test_preflight_rejects_nonempty_target_that_would_block_move(tmp_path):
    marker = _setup(tmp_path)
    _database(tmp_path / "data" / "ratslotse.sqlite", "web_users", rows=0)

    with pytest.raises(PreflightError, match="enthält keine Zeilen|blockiert"):
        verify(tmp_path, marker)


def test_preflight_rejects_wrong_target_name_for_old_account_database(tmp_path):
    marker = _setup(tmp_path)
    (tmp_path / ".env").write_text(
        "RATSLOTSE_DB=data/accounts.sqlite\nNWZ_DB=data/nwz.sqlite\n",
        encoding="utf-8",
    )

    with pytest.raises(PreflightError, match="namens ratslotse.sqlite"):
        verify(tmp_path, marker)


def test_preflight_rejects_backup_older_than_deploy_marker(tmp_path):
    marker = _setup(tmp_path, account_name="ratslotse.sqlite")
    council_backup = tmp_path / "data" / "backups" / "council_2026-09-03.sqlite"
    old = marker.stat().st_mtime_ns - 1
    os.utime(council_backup, ns=(old, old))

    with pytest.raises(PreflightError, match="nicht in diesem Deploy-Lauf"):
        verify(tmp_path, marker)


def test_preflight_rejects_backup_with_same_timestamp_as_marker(tmp_path):
    marker = _setup(tmp_path, account_name="ratslotse.sqlite")
    council_backup = tmp_path / "data" / "backups" / "council_2026-09-03.sqlite"
    same = marker.stat().st_mtime_ns
    os.utime(council_backup, ns=(same, same))

    with pytest.raises(PreflightError, match="nicht in diesem Deploy-Lauf"):
        verify(tmp_path, marker)


def test_preflight_rejects_backup_with_different_row_count(tmp_path):
    marker = _setup(tmp_path, account_name="ratslotse.sqlite")
    backup = tmp_path / "data" / "backups" / "council_2026-09-03.sqlite"
    with sqlite3.connect(backup) as connection:
        connection.execute("INSERT INTO council_sessions (id) VALUES (99)")

    with pytest.raises(PreflightError, match="abweichendes Tabellenmanifest"):
        verify(tmp_path, marker)


def test_runtime_preflight_accepts_required_configuration_and_crons():
    build, video_model, stt_model = verify_configuration(
        {"APP_MIN_BUILD": "19", "OPENROUTER_API_KEY": "not-printed"}, 19
    )
    verify_crontab(
        "30 10 * * * cd /srv/app && .venv/bin/python "
        "scripts/check_council_videos.py\n"
        "0 13 * * * cd /srv/app && .venv/bin/python "
        "scripts/record_council_livestream.py\n"
    )

    assert build == 19
    assert video_model == "openai/gpt-5.6-luna"
    assert stt_model == "google/gemini-2.5-flash"


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"APP_MIN_BUILD": "18", "OPENROUTER_API_KEY": "key"}, "mindestens 19"),
        ({"APP_MIN_BUILD": "19"}, "OPENROUTER_API_KEY"),
        (
            {
                "APP_MIN_BUILD": "19",
                "OPENROUTER_API_KEY": "key",
                "COUNCIL_STT_MODEL": "",
            },
            "COUNCIL_STT_MODEL",
        ),
    ],
)
def test_runtime_preflight_rejects_invalid_configuration(values, message):
    with pytest.raises(RuntimePreflightError, match=message):
        verify_configuration(values, 19)


def test_runtime_preflight_rejects_missing_or_wrong_cron():
    with pytest.raises(RuntimePreflightError, match="record_council_livestream.py"):
        verify_crontab(
            "30 10 * * * cd /srv/app && .venv/bin/python "
            "scripts/check_council_videos.py\n"
        )

    with pytest.raises(RuntimePreflightError, match="verwendet nicht"):
        verify_crontab(
            "30 10 * * * python scripts/check_council_videos.py\n"
            "0 13 * * * .venv/bin/python scripts/record_council_livestream.py\n"
        )


def test_runtime_preflight_rejects_livestream_cron_that_is_late_in_summer():
    """16 Uhr UTC wäre in Oldenburg im Sommer erst 18 Uhr Ortszeit."""
    with pytest.raises(RuntimePreflightError, match="record_council_livestream.py"):
        verify_crontab(
            "30 10 * * * .venv/bin/python scripts/check_council_videos.py\n"
            "0 16 * * * .venv/bin/python scripts/record_council_livestream.py\n"
        )


def test_runtime_preflight_rejects_duplicate_video_cron():
    with pytest.raises(RuntimePreflightError, match="2-mal aktiv"):
        verify_crontab(
            "30 10 * * * .venv/bin/python scripts/check_council_videos.py\n"
            "30 10 * * * cd /srv/app && .venv/bin/python "
            "scripts/check_council_videos.py\n"
            "0 13 * * * .venv/bin/python scripts/record_council_livestream.py\n"
        )


def test_runtime_preflight_checks_exact_passwordless_systemd_commands(monkeypatch):
    run = Mock(
        return_value=subprocess.CompletedProcess(
            [],
            0,
            "Sudoers entry: /etc/sudoers.d/tim-nwz\n"
            "    RunAsUsers: ALL\n"
            "    Options: !authenticate\n"
            "    Commands:\n"
            "        /bin/systemctl\n",
            "",
        )
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        run,
    )

    verify_systemd_permissions()

    assert run.call_args_list == [
        call(
            ["sudo", "-n", "-ll", "/bin/systemctl", "stop", "nwz-web-api"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "LC_ALL": "C"},
        ),
        call(
            ["sudo", "-n", "-ll", "/bin/systemctl", "start", "nwz-web-api"],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "LC_ALL": "C"},
        ),
        call(
            [
                "sudo",
                "-n",
                "-ll",
                "/bin/systemctl",
                "restart",
                "nwz-web-frontend",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "LC_ALL": "C"},
        ),
    ]


def test_runtime_preflight_rejects_missing_systemd_permission(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "denied"),
    )

    with pytest.raises(RuntimePreflightError, match="stop nwz-web-api"):
        verify_systemd_permissions()


def test_runtime_preflight_rejects_allowed_but_passworded_systemd_rule(monkeypatch):
    """Ein erfolgreicher list-Aufruf beweist ohne !authenticate kein NOPASSWD."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            "Sudoers entry: /etc/sudoers\n"
            "    RunAsUsers: ALL\n"
            "    Options: authenticate\n"
            "    Matched: /bin/systemctl stop nwz-web-api\n",
            "",
        ),
    )

    with pytest.raises(RuntimePreflightError, match="NOPASSWD.*stop nwz-web-api"):
        verify_systemd_permissions()


def test_process_scan_finds_old_repo_python_process(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    proc_root = tmp_path / "proc"
    process = proc_root / "4711"
    process.mkdir(parents=True)
    (process / "cmdline").write_bytes(
        b"/usr/bin/python3\0scripts/check_council.py\0"
    )
    (process / "cwd").symlink_to(root, target_is_directory=True)

    assert running_repo_python_processes(
        root, proc_root=proc_root, own_pid=9999
    ) == [(4711, "check_council.py")]


def test_handle_scan_finds_database_opened_outside_repo(tmp_path):
    database = tmp_path / "app" / "data" / "council.sqlite"
    database.parent.mkdir(parents=True)
    database.touch()
    proc_root = tmp_path / "proc"
    descriptors = proc_root / "815" / "fd"
    descriptors.mkdir(parents=True)
    (descriptors / "4").symlink_to(database)

    assert prepare_release_databases.open_database_handles(
        [database], proc_root=proc_root, own_pid=9999
    ) == [(815, "council.sqlite")]


def test_release_snapshot_lock_blocks_concurrent_writer(tmp_path):
    database = tmp_path / "ratslotse.sqlite"
    _database(database, "web_users")
    source = prepare_release_databases.inspect_database(database, "web_users")

    locks = prepare_release_databases._lock_sources([source])
    try:
        writer = sqlite3.connect(database, timeout=0)
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                writer.execute("INSERT INTO web_users (id) VALUES (2)")
        finally:
            writer.close()
    finally:
        prepare_release_databases._release_locks(locks)


def test_maintenance_marker_blocks_both_stores(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / MARKER_NAME).touch()

    with pytest.raises(RuntimeError, match="Release-Wartung aktiv"):
        Store(data / "ratslotse.sqlite")
    with pytest.raises(RuntimeError, match="Release-Wartung aktiv"):
        CouncilStore(data / "council.sqlite")
    assert not (data / "ratslotse.sqlite").exists()
    assert not (data / "council.sqlite").exists()


def test_release_preparation_requires_marker_and_explicit_bypass(
    tmp_path, monkeypatch
):
    data = tmp_path / "data"
    data.mkdir()
    account_store = Store(data / "nwz.sqlite")
    account_store.create_web_user("release@example.org", "hash")
    account_store.close()
    council_store = CouncilStore(
        data / "council.sqlite", ratslotse_db_path=data / "nwz.sqlite"
    )
    council_store.save_session(
        CouncilSession(4702, "Rat", "2026-09-03", "17:00", "Rathaus")
    )
    council_store.close()

    monkeypatch.delenv(BYPASS_ENV, raising=False)
    with pytest.raises(RuntimeError, match="Wartungsmarker fehlt"):
        prepare_release_databases.prepare(tmp_path, "test")

    (data / MARKER_NAME).touch()
    with pytest.raises(RuntimeError, match="Explizite Freigabe"):
        prepare_release_databases.prepare(tmp_path, "test")

    monkeypatch.setenv(BYPASS_ENV, "1")
    monkeypatch.setattr(
        prepare_release_databases, "verify_quiescent", lambda root: None
    )
    monkeypatch.setattr(
        prepare_release_databases, "open_database_handles", lambda paths: []
    )
    account, council, manifest = prepare_release_databases.prepare(tmp_path, "test")
    assert account.is_file() and council.is_file() and manifest.is_file()
    assert not (data / "nwz.sqlite").exists()
    assert (data / "backups" / "nwz_predeploy_test.sqlite").is_file()
    assert (data / "backups" / "council_predeploy_test.sqlite").is_file()
    assert (data / MARKER_NAME).is_file(), "nur der Workflow hebt die Barriere auf"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    assert {entry["source"] for entry in document["databases"]} == {
        "nwz.sqlite",
        "council.sqlite",
    }
    assert all(len(entry["sha256"]) == 64 for entry in document["databases"])


def test_workflow_guards_final_backup_and_migrations_at_cutover():
    workflow = Path(".github/workflows/deploy.yml").read_text(encoding="utf-8")

    assert workflow.index("Create and verify pre-transfer rollback baseline") < workflow.index(
        "Verify release runtime prerequisites"
    ) < workflow.index("Deploy via rsync")
    assert "< scripts/verify_predeploy_backup.py" in workflow
    assert "< scripts/verify_release_runtime.py" in workflow
    assert workflow.index("Enter release maintenance barrier") < workflow.index(
        "Deploy via rsync"
    )
    assert workflow.index("set -o noclobber") < workflow.index(
        "Deploy via rsync"
    ) < workflow.index("sudo /bin/systemctl stop nwz-web-api") < workflow.index(
        "--require-quiescent"
    )
    assert workflow.index('snapshot_label="deploy_') < workflow.index(
        "scripts/prepare_release_databases.py"
    ) < workflow.index("--snapshot-label") < workflow.index('rm -f "$wartung"')
    assert workflow.index('rm -f "$wartung"') < workflow.index(
        "sudo /bin/systemctl start nwz-web-api"
    ) < workflow.index("sudo /bin/systemctl restart nwz-web-frontend")
