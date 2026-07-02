"""Tests for web-account creation and Telegram linking via /verbinden."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from nwz.bot_commands import handle_update
from nwz.store import Store

CHAT_ID = 777


def _msg(chat_id: int, text: str, first_name: str = "Tim") -> dict:
    return {"message": {"chat": {"id": chat_id}, "from": {"first_name": first_name}, "text": text}}


@pytest.fixture
def store_path(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "testtoken")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "99999")
    return tmp_path / "nwz.sqlite"


def test_web_user_crud(store_path):
    store = Store(store_path)
    uid = store.create_web_user("a@b.de", "hash", "user")
    assert store.count_web_users() == 1
    u = store.get_web_user_by_email("A@B.de")  # case-insensitive
    assert u["id"] == uid and u["role"] == "user"
    store.set_web_user_role(uid, "admin")
    assert store.get_web_user_by_id(uid)["role"] == "admin"
    store.close()


def test_redeem_valid_code_links_and_whitelists(store_path):
    store = Store(store_path)
    uid = store.create_web_user("a@b.de", "hash")
    store.create_link_code(uid, "ABC123", ttl_minutes=15)
    email = store.redeem_link_code("ABC123", CHAT_ID, "Tim")
    assert email == "a@b.de"
    assert store.is_user(CHAT_ID)  # whitelisted
    assert store.get_web_user_by_id(uid)["telegram_chat_id"] == CHAT_ID
    # code is single-use
    assert store.redeem_link_code("ABC123", CHAT_ID) is None
    store.close()


def test_redeem_unknown_code(store_path):
    store = Store(store_path)
    assert store.redeem_link_code("NOPE", CHAT_ID) is None
    assert not store.is_user(CHAT_ID)
    store.close()


def test_redeem_expired_code(store_path):
    store = Store(store_path)
    uid = store.create_web_user("a@b.de", "hash")
    past = (datetime.utcnow() - timedelta(minutes=1)).isoformat(timespec="seconds")
    now = datetime.utcnow().isoformat(timespec="seconds")
    store._conn.execute(
        "INSERT INTO link_codes (code, web_user_id, created_at, expires_at) VALUES (?,?,?,?)",
        ("OLD123", uid, now, past),
    )
    store._conn.commit()
    assert store.redeem_link_code("OLD123", CHAT_ID) is None
    store.close()


def test_create_link_code_replaces_previous(store_path):
    store = Store(store_path)
    uid = store.create_web_user("a@b.de", "hash")
    store.create_link_code(uid, "FIRST1")
    store.create_link_code(uid, "SECOND")
    assert store.redeem_link_code("FIRST1", CHAT_ID) is None  # replaced
    assert store.redeem_link_code("SECOND", CHAT_ID) == "a@b.de"
    store.close()


def test_remove_user_unlinks_web_account(store_path):
    store = Store(store_path)
    uid = store.create_web_user("a@b.de", "hash")
    store.create_link_code(uid, "ABC123")
    store.redeem_link_code("ABC123", CHAT_ID)
    store.remove_user(CHAT_ID)
    assert not store.is_user(CHAT_ID)
    assert store.get_web_user_by_id(uid)["telegram_chat_id"] is None
    store.close()


@patch("nwz.bot_commands.reply")
def test_verbinden_command_success(mock_reply, store_path):
    store = Store(store_path)
    uid = store.create_web_user("a@b.de", "hash")
    store.create_link_code(uid, "ABC123")
    store.close()
    handle_update(_msg(CHAT_ID, "/verbinden ABC123"), store_path)
    text = mock_reply.call_args[0][1]
    assert "Verbunden" in text and "a@b.de" in text
    store = Store(store_path)
    assert store.is_user(CHAT_ID)
    store.close()


@patch("nwz.bot_commands.reply")
def test_verbinden_command_invalid_code(mock_reply, store_path):
    Store(store_path).close()
    handle_update(_msg(CHAT_ID, "/verbinden WRONG1"), store_path)
    assert "ungültig" in mock_reply.call_args[0][1].lower()


@patch("nwz.bot_commands.reply")
def test_verbinden_command_without_code_shows_usage(mock_reply, store_path):
    Store(store_path).close()
    handle_update(_msg(CHAT_ID, "/verbinden"), store_path)
    assert "/verbinden" in mock_reply.call_args[0][1]


@patch("nwz.bot_commands.reply")
def test_verbinden_works_before_whitelisting(mock_reply, store_path):
    # A brand-new chat (not whitelisted) must still be able to redeem a code.
    store = Store(store_path)
    uid = store.create_web_user("new@b.de", "hash")
    store.create_link_code(uid, "JOIN12")
    store.close()
    handle_update(_msg(99888, "/verbinden JOIN12"), store_path)
    assert "Verbunden" in mock_reply.call_args[0][1]
