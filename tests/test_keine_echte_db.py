"""Wächter: Die Testsuite schreibt nie in die Datenbanken unter ``data/``.

Anlass: ``kern/usage.py`` fällt ohne ``RATSLOTSE_SQLITE`` auf
``data/ratslotse.sqlite`` des Checkouts zurück. Tests, die ``chat_complete``
mit ``_feature`` riefen, legten dort bei jedem Lauf erfundene Kostenzeilen ab
(23.09.2026: acht je Lauf), die im Admin-Panel unter LLM-Kosten erschienen.
Weil ``usage.record`` Fehler bewusst schluckt, genügt der Wächter in
``conftest.py`` allein nicht — der Kostenpfad wird hier eigens geprüft.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from kern import llm, usage

DATA_DIR = (Path(__file__).resolve().parent.parent / "data").resolve()


def test_kostendatei_liegt_nicht_unter_data():
    assert not Path(usage._db()).resolve().is_relative_to(DATA_DIR)


@pytest.mark.parametrize("ziel", [
    str(DATA_DIR / "ratslotse.sqlite"),
    DATA_DIR / "council.sqlite",
    f"file:{DATA_DIR / 'ratslotse.sqlite'}?mode=rwc",
])
def test_connect_auf_data_wird_abgewiesen(ziel):
    kwargs = {"uri": True} if str(ziel).startswith("file:") else {}
    with pytest.raises(RuntimeError, match="echte Datenbank"):
        sqlite3.connect(ziel, **kwargs)


def test_tmp_und_memory_bleiben_erlaubt(tmp_path):
    sqlite3.connect(":memory:").close()
    sqlite3.connect(tmp_path / "x.sqlite").close()


def test_nur_lesend_bleibt_erlaubt(tmp_path, monkeypatch):
    """Die Messtests lesen den echten Bestand mit ``mode=ro`` — das darf sein."""
    from tests import conftest
    monkeypatch.setattr(conftest, "DATA_DIR", tmp_path.resolve())
    datei = tmp_path / "echt.sqlite"
    conftest._echtes_connect(datei).close()
    sqlite3.connect(f"file:{datei}?mode=ro", uri=True).close()
    with pytest.raises(RuntimeError):
        sqlite3.connect(datei)


@pytest.mark.parametrize("variable", ["RATSLOTSE_DB", "COUNCIL_DB", "RATSLOTSE_SQLITE",
                                      "CITIES_DB", "CITIES_FILES_DIR", "CITIES_RAW_DIR"])
def test_umgebung_zeigt_nicht_nach_data(variable):
    import os
    assert not Path(os.environ[variable]).resolve().is_relative_to(DATA_DIR)


def test_llm_aufruf_mit_feature_schreibt_in_die_testdatei():
    """Der Weg, auf dem die Zeilen entstanden: ``_record_usage`` ohne Stub."""
    vorher = _zeilen()
    llm._record_usage("guard_test", "m", SimpleNamespace(prompt_tokens=3, completion_tokens=4))
    assert _zeilen() == vorher + 1


def _zeilen() -> int:
    try:
        con = sqlite3.connect(usage._db())
    except RuntimeError:
        pytest.fail("usage._db() zeigt nach data/")
    try:
        return con.execute(
            "SELECT COUNT(*) FROM llm_usage WHERE feature = 'guard_test'").fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    finally:
        con.close()
