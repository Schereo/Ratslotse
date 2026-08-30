"""Regressionstest für scripts/remind_setup.py.

Der Job war seit dem Bau kaputt und niemandem fiel es auf: `Store()` wurde ohne
Pfad aufgerufen und warf bei JEDEM Lauf sofort einen TypeError — noch bevor
überhaupt geprüft wurde, ob es Kandidaten gibt. Zusätzlich fehlte `load_dotenv`,
sodass unter Cron nie ein RESEND_API_KEY gesetzt war und selbst die
Absturz-Meldung von `run_guarded` nicht rausgehen konnte.

Der Test ruft `main()` einmal echt auf. Er braucht keinen Mailversand: Ohne
Schlüssel nimmt die Funktion den dokumentierten „kein_mailversand"-Zweig — was
sie eben NUR erreicht, wenn sie vorher nicht abstürzt.
"""
import importlib.util
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from kern.store import Store

ROOT = Path(__file__).resolve().parent.parent


def _load(db_path: Path):
    """remind_setup.py als Modul laden (es liegt in scripts/, ist kein Paket)."""
    os.environ["RATSLOTSE_DB"] = str(db_path)
    spec = importlib.util.spec_from_file_location(
        "remind_setup_under_test", ROOT / "scripts" / "remind_setup.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = tmp_path / "ratslotse.sqlite"
    Store(path)  # legt Schema an
    monkeypatch.setenv("RATSLOTSE_DB", str(path))
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    return path


def test_main_laeuft_ohne_kandidaten_durch(db):
    """Der Lauf darf nicht abstürzen — genau das tat er vorher."""
    mod = _load(db)
    result = mod.main()
    assert isinstance(result, dict)
    assert result["kandidaten"] == 0 and result["gesendet"] == 0


def test_main_findet_offene_einrichtung(db):
    """Mit einem Kandidaten muss der Job ihn sehen. Ohne Mail-Schlüssel meldet
    er das ausdrücklich, statt die Kandidaten still als erinnert zu markieren."""
    store = Store(db)
    store.create_web_user("offen@test.de", "hash", display_name="Offen")
    alt = (datetime.utcnow() - timedelta(days=3)).isoformat(timespec="seconds")
    with store._conn:
        store._conn.execute(
            "UPDATE web_users SET status='active', email_verified=1, setup_step=1, "
            "setup_started_at=?, setup_done_at=NULL, setup_reminded_at=NULL "
            "WHERE email='offen@test.de'", (alt,))

    mod = _load(db)
    result = mod.main()
    assert result["kandidaten"] == 1
    assert result["gesendet"] == 0
    assert result["grund"] == "kein_mailversand"

    # Wichtig: ohne Versand darf niemand als „erinnert" markiert werden,
    # sonst verlöre man den Kandidaten stillschweigend.
    row = store._conn.execute(
        "SELECT setup_reminded_at FROM web_users WHERE email='offen@test.de'").fetchone()
    assert row[0] is None


def test_laedt_dotenv():
    """Ohne load_dotenv ist unter Cron kein RESEND_API_KEY gesetzt — dann geht
    weder die Erinnerung noch die Absturzmeldung raus."""
    quelltext = (ROOT / "scripts" / "remind_setup.py").read_text()
    assert "load_dotenv" in quelltext
