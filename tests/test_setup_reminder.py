"""Einrichtungs-Assistent: Fortschritt am Konto + einmalige Erinnerung (26a).

Der Stand wandert vom Gerät ans Konto, damit er eine Neuinstallation übersteht
— und damit ``scripts/remind_setup.py`` erkennen kann, wer angefangen und nicht
zu Ende gebracht hat. Die Mail geht genau einmal; alles hier prüft vor allem,
dass sie NICHT geht, wenn sie nicht soll.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nwz.store import Store  # noqa: E402


@pytest.fixture
def store():
    path = Path(tempfile.mkdtemp()) / "nwz.sqlite"
    os.environ["NWZ_DB"] = str(path)
    return Store(str(path))


def _user(store: Store, email: str = "a@test.de") -> int:
    uid = store.create_web_user(email, "hash", "user", "active", email_verified=True)
    return uid


def _backdate(store: Store, uid: int, hours: int) -> None:
    """Die Uhr zurückdrehen, statt im Test zu warten."""
    old = (datetime.utcnow() - timedelta(hours=hours)).isoformat(timespec="seconds")
    with store._conn:  # noqa: SLF001 — Testfixture darf ans Innenleben
        store._conn.execute(  # noqa: SLF001
            "UPDATE web_users SET setup_started_at = ?, setup_updated_at = ? WHERE id = ?",
            (old, old, uid),
        )


def test_step_is_persisted(store):
    uid = _user(store)
    assert store.get_setup(uid) == {"step": 0, "started_at": None, "done_at": None}
    store.set_setup_step(uid, 2)
    saved = store.get_setup(uid)
    assert saved["step"] == 2 and saved["started_at"] and saved["done_at"] is None


def test_start_time_stays_at_the_first_step(store):
    """``setup_started_at`` markiert den Beginn — spätere Schritte verschieben
    ihn nicht, sonst rutschte die Frist mit jedem Tippen nach hinten."""
    uid = _user(store)
    store.set_setup_step(uid, 1)
    first = store.get_setup(uid)["started_at"]
    store.set_setup_step(uid, 2)
    assert store.get_setup(uid)["started_at"] == first


def test_reminder_only_for_abandoned_setups(store):
    fresh = _user(store, "fresh@test.de")      # gerade erst angefangen
    store.set_setup_step(fresh, 1)
    stale = _user(store, "stale@test.de")      # vor drei Tagen liegen gelassen
    store.set_setup_step(stale, 2)
    _backdate(store, stale, 72)
    done = _user(store, "done@test.de")        # fertig eingerichtet
    store.set_setup_step(done, 3, done=True)
    _backdate(store, done, 72)
    greeted = _user(store, "greeted@test.de")  # nur den Gruß gesehen (Schritt 0)
    store.set_setup_step(greeted, 0)
    _backdate(store, greeted, 72)
    untouched = _user(store, "nix@test.de")    # war nie im Assistenten

    ids = {u["id"] for u in store.setups_to_remind(older_than_hours=48)}
    assert ids == {stale}
    assert fresh not in ids and done not in ids and greeted not in ids
    assert untouched not in ids


def test_reminder_is_sent_only_once(store):
    uid = _user(store)
    store.set_setup_step(uid, 1)
    _backdate(store, uid, 72)
    assert [u["id"] for u in store.setups_to_remind()] == [uid]
    store.mark_setup_reminded(uid)
    assert store.setups_to_remind() == []


def test_activity_resets_the_clock(store):
    """Wer vor Tagen anfing, aber eben noch getippt hat, ist nicht liegengeblieben."""
    uid = _user(store)
    store.set_setup_step(uid, 1)
    _backdate(store, uid, 72)
    store.set_setup_step(uid, 2)  # frische Bewegung
    assert store.setups_to_remind(older_than_hours=48) == []


def test_unverified_and_pending_accounts_are_spared(store):
    """Wer die Adresse nie bestätigt hat, bekommt keine Werbung dorthin."""
    unverified = store.create_web_user("u@test.de", "h", "user", "active", email_verified=False)
    pending = store.create_web_user("p@test.de", "h", "user", "pending", email_verified=True)
    for uid in (unverified, pending):
        store.set_setup_step(uid, 2)
        _backdate(store, uid, 72)
    assert store.setups_to_remind() == []
