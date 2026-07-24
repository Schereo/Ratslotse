"""Cron-Protokoll: run_guarded schreibt jeden Lauf in job_runs (nwz/alerts.py)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nwz.alerts import run_guarded  # noqa: E402
from nwz.jobs import BY_KEY, JOBS  # noqa: E402
from nwz.store import Store  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Temporäre nwz.sqlite — run_guarded findet sie über NWZ_DB."""
    path = tmp_path / "nwz.sqlite"
    Store(path).close()
    monkeypatch.setenv("NWZ_DB", str(path))
    return path


def test_erfolgreicher_lauf_wird_mit_kennzahlen_protokolliert(db):
    run_guarded("check_council", lambda: {"Benachrichtigungen": 3})

    store = Store(db)
    runs = store.job_runs()
    store.close()

    assert len(runs) == 1
    run = runs[0]
    assert run["job"] == "check_council"
    assert run["status"] == "ok"
    assert run["stats"] == {"Benachrichtigungen": 3}
    assert run["error"] is None
    assert run["duration_s"] >= 0
    assert run["finished_at"] >= run["started_at"]


def test_lauf_ohne_rueckgabe_wird_ohne_kennzahlen_protokolliert(db):
    run_guarded("backup_db", lambda: None)

    store = Store(db)
    runs = store.job_runs()
    store.close()
    assert runs[0]["status"] == "ok" and runs[0]["stats"] is None


def test_absturz_wird_protokolliert_und_weitergereicht(db, monkeypatch):
    # Ohne Mail-Konfiguration bleibt der Alarm ein Log-Eintrag; der Crash muss
    # trotzdem als Fehlerlauf in der Historie landen und weiterfliegen.
    monkeypatch.delenv("ALERT_EMAIL", raising=False)
    monkeypatch.delenv("WEB_ADMIN_EMAIL", raising=False)

    def boom():
        raise RuntimeError("Ratsinfo nicht erreichbar")

    with pytest.raises(RuntimeError):
        run_guarded("check_protocols", boom)

    store = Store(db)
    runs = store.job_runs()
    store.close()
    assert runs[0]["status"] == "error"
    assert "Ratsinfo nicht erreichbar" in runs[0]["error"]
    assert runs[0]["stats"] is None


def test_job_runs_filtert_nach_job_und_sortiert_neueste_zuerst(db):
    run_guarded("check_council", lambda: {"n": 1})
    run_guarded("backup_db", lambda: None)
    run_guarded("check_council", lambda: {"n": 2})

    store = Store(db)
    council = store.job_runs(job="check_council")
    store.close()

    assert [r["stats"]["n"] for r in council] == [2, 1]


def test_registry_deckt_die_cron_eintraege_ab():
    """Die Übersicht kann nur zeigen, was in der Registry steht — jeder Job aus
    der crontab braucht dort einen Eintrag mit Takt und Toleranz."""
    assert {j["key"] for j in JOBS} == {
        "check_council", "check_committees", "check_protocols", "weekly_enrich",
        "remind_setup", "backup_db",
    }
    for job in JOBS:
        assert BY_KEY[job["key"]] is job
        assert job["max_age_h"] > 0 and job["label"] and job["schedule"]
