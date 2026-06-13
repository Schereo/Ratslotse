from __future__ import annotations

import os
import pytest
from datetime import date, timedelta
from unittest.mock import patch, call

from nwz.bot_commands import _committee_buttons, handle_update, handle_callback_query
from nwz.store import Store
from council.store import CouncilStore
from council.scraper import CouncilSession, AgendaItem

FUTURE_DATE = (date.today() + timedelta(days=14)).isoformat()

CHAT_ID = 12345
COMMITTEES = [
    "Ausschuss für Stadtplanung",  # idx 1
    "Bauausschuss",                # idx 2
    "Finanzausschuss",             # idx 3
]


def _make_msg(chat_id: int, text: str) -> dict:
    return {"message": {"chat": {"id": chat_id}, "text": text}}


def _make_cq(chat_id: int, message_id: int, data: str) -> dict:
    return {
        "callback_query": {
            "id": "cq1",
            "from": {"id": chat_id},
            "message": {"message_id": message_id},
            "data": data,
        }
    }


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "testtoken")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "99999")

    nwz_path = tmp_path / "nwz.sqlite"
    store = Store(nwz_path)
    store.add_user(CHAT_ID, "testuser")
    store.close()

    council_path = tmp_path / "council.sqlite"
    cs = CouncilStore(council_path)
    for i, name in enumerate(COMMITTEES, 1):
        cs.save_session(CouncilSession(i, name, f"2024-01-0{i}", "19:00", "Rathaus"))
    cs.close()

    return nwz_path


# ---------------------------------------------------------------------------
# _committee_buttons
# ---------------------------------------------------------------------------

class TestCommitteeButtons:
    def test_max_four_per_row(self):
        names = [f"Ausschuss {i}" for i in range(10)]
        buttons = _committee_buttons(names, set())
        assert len(buttons) == 3          # 4 + 4 + 2
        assert len(buttons[0]) == 4
        assert len(buttons[1]) == 4
        assert len(buttons[2]) == 2

    def test_labels_subscribed_and_not(self):
        names = ["Alpha", "Beta", "Gamma"]
        buttons = _committee_buttons(names, {"Beta"})
        flat = [b for row in buttons for b in row]
        assert flat[0]["text"] == "➕ 1"
        assert flat[1]["text"] == "✅ 2"
        assert flat[2]["text"] == "➕ 3"

    def test_callback_data_under_64_bytes(self):
        long_name = "Ausschuss für Klimaschutz, Umwelt, Mobilität und Stadtplanung"
        names = [long_name] * 20
        buttons = _committee_buttons(names, set())
        for row in buttons:
            for btn in row:
                assert len(btn["callback_data"].encode("utf-8")) < 64

    def test_callback_data_uses_index(self):
        names = ["Alpha", "Beta"]
        buttons = _committee_buttons(names, set())
        flat = [b for row in buttons for b in row]
        assert flat[0]["callback_data"] == "ctoggle:1"
        assert flat[1]["callback_data"] == "ctoggle:2"

    def test_empty_list(self):
        assert _committee_buttons([], set()) == []


# ---------------------------------------------------------------------------
# /committees handler
# ---------------------------------------------------------------------------

class TestCommitteesCommand:
    @patch("nwz.bot_commands.reply")
    @patch("nwz.bot_commands.reply_with_buttons")
    def test_empty_db_shows_no_committees(self, mock_rwb, mock_reply, tmp_path, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "testtoken")
        nwz_path = tmp_path / "nwz.sqlite"
        store = Store(nwz_path)
        store.add_user(CHAT_ID, "testuser")
        store.close()
        # No council data → CouncilStore creates empty DB
        handle_update(_make_msg(CHAT_ID, "/committees"), nwz_path)
        mock_reply.assert_called_once()
        assert "Keine" in mock_reply.call_args[0][1]
        mock_rwb.assert_not_called()

    @patch("nwz.bot_commands.reply_with_buttons", return_value=42)
    def test_with_data_sends_buttons(self, mock_rwb, data_dir):
        handle_update(_make_msg(CHAT_ID, "/committees"), data_dir)
        mock_rwb.assert_called_once()
        _chat_id, text, buttons = mock_rwb.call_args[0]
        assert _chat_id == CHAT_ID
        assert len(buttons) > 0

    @patch("nwz.bot_commands.reply_with_buttons", return_value=42)
    def test_list_shows_number_and_name(self, mock_rwb, data_dir):
        handle_update(_make_msg(CHAT_ID, "/committees"), data_dir)
        text = mock_rwb.call_args[0][1]
        assert "1." in text
        assert "2." in text
        assert "3." in text
        assert "Ausschuss für Stadtplanung" in text
        assert "Bauausschuss" in text
        assert "Finanzausschuss" in text

    @patch("nwz.bot_commands.reply_with_buttons", return_value=42)
    def test_subscribed_shows_checkmark(self, mock_rwb, data_dir):
        store = Store(data_dir)
        store.subscribe(CHAT_ID, "Bauausschuss")
        store.close()
        handle_update(_make_msg(CHAT_ID, "/committees"), data_dir)
        text = mock_rwb.call_args[0][1]
        assert "✅" in text
        assert "➕" in text

    @patch("nwz.bot_commands.reply")
    @patch("nwz.bot_commands.reply_with_buttons", return_value=None)
    def test_fallback_to_reply_when_buttons_fail(self, mock_rwb, mock_reply, data_dir):
        handle_update(_make_msg(CHAT_ID, "/committees"), data_dir)
        mock_rwb.assert_called_once()
        mock_reply.assert_called_once()
        text = mock_reply.call_args[0][1]
        assert "Ausschuss" in text

    @patch("nwz.bot_commands.reply_with_buttons", return_value=42)
    def test_message_fits_in_single_call(self, mock_rwb, data_dir):
        handle_update(_make_msg(CHAT_ID, "/committees"), data_dir)
        text = mock_rwb.call_args[0][1]
        assert len(text) < 4096


# ---------------------------------------------------------------------------
# /check
# ---------------------------------------------------------------------------

class TestCheckCommand:
    @patch("nwz.bot_commands.reply")
    def test_no_subscriptions(self, mock_reply, data_dir):
        handle_update(_make_msg(CHAT_ID, "/check"), data_dir)
        mock_reply.assert_called_once()
        assert "keine" in mock_reply.call_args[0][1].lower()

    @patch("nwz.bot_commands.reply")
    def test_no_upcoming_sessions(self, mock_reply, data_dir):
        # data_dir fixture adds sessions with past dates → upcoming_sessions() returns nothing
        store = Store(data_dir)
        store.subscribe(CHAT_ID, COMMITTEES[0])
        store.close()
        handle_update(_make_msg(CHAT_ID, "/check"), data_dir)
        mock_reply.assert_called_once()
        text = mock_reply.call_args[0][1]
        assert "Bisher" in text or "keine" in text.lower()

    @patch("nwz.bot_commands.reply")
    def test_no_sessions_for_subscribed_committee(self, mock_reply, data_dir):
        cs = CouncilStore(data_dir.parent / "council.sqlite")
        cs.save_session(CouncilSession(100, "Anderer Ausschuss", FUTURE_DATE, "18:00", "Rathaus"))
        cs.close()
        store = Store(data_dir)
        store.subscribe(CHAT_ID, COMMITTEES[0])
        store.close()
        handle_update(_make_msg(CHAT_ID, "/check"), data_dir)
        mock_reply.assert_called_once()
        assert "keine" in mock_reply.call_args[0][1].lower()

    @patch("council.committee_summary.summarize_agenda", return_value="<b>GPT-Summary</b>")
    @patch("nwz.bot_commands.reply")
    def test_sends_summary(self, mock_reply, mock_summarize, data_dir):
        cs = CouncilStore(data_dir.parent / "council.sqlite")
        session = CouncilSession(
            100, COMMITTEES[0], FUTURE_DATE, "18:00", "Rathaus",
            agenda_items=[AgendaItem("Ö 1", "Wichtiges Thema")],
        )
        cs.save_session(session)
        cs.close()
        store = Store(data_dir)
        store.subscribe(CHAT_ID, COMMITTEES[0])
        store.close()
        handle_update(_make_msg(CHAT_ID, "/check"), data_dir)
        texts = [c[0][1] for c in mock_reply.call_args_list]
        assert any("<b>GPT-Summary</b>" in t for t in texts)

    @patch("council.committee_summary.summarize_agenda", return_value="")
    @patch("nwz.bot_commands.reply")
    def test_routine_only_fallback(self, mock_reply, mock_summarize, data_dir):
        cs = CouncilStore(data_dir.parent / "council.sqlite")
        session = CouncilSession(
            100, COMMITTEES[0], FUTURE_DATE, "18:00", "Rathaus",
            agenda_items=[AgendaItem("Ö 1", "Genehmigung der Tagesordnung")],
        )
        cs.save_session(session)
        cs.close()
        store = Store(data_dir)
        store.subscribe(CHAT_ID, COMMITTEES[0])
        store.close()
        handle_update(_make_msg(CHAT_ID, "/check"), data_dir)
        texts = [c[0][1] for c in mock_reply.call_args_list]
        assert any("Routine" in t for t in texts)

    @patch("council.committee_summary.summarize_agenda", return_value="<b>Summary</b>")
    @patch("nwz.bot_commands.reply")
    def test_does_not_mark_notified(self, mock_reply, mock_summarize, data_dir):
        cs = CouncilStore(data_dir.parent / "council.sqlite")
        session = CouncilSession(
            100, COMMITTEES[0], FUTURE_DATE, "18:00", "Rathaus",
            agenda_items=[AgendaItem("Ö 1", "Wichtiges Thema")],
        )
        cs.save_session(session)
        cs.close()
        store = Store(data_dir)
        store.subscribe(CHAT_ID, COMMITTEES[0])
        store.close()
        handle_update(_make_msg(CHAT_ID, "/check"), data_dir)
        cs = CouncilStore(data_dir.parent / "council.sqlite")
        assert not cs.was_notified(100, CHAT_ID)
        cs.close()


# ---------------------------------------------------------------------------
# handle_callback_query
# ---------------------------------------------------------------------------

class TestCallbackQuery:
    @patch("nwz.bot_commands.edit_message_buttons")
    @patch("nwz.bot_commands.answer_callback_query")
    def test_subscribe_via_button(self, mock_answer, mock_edit, data_dir):
        handle_callback_query(_make_cq(CHAT_ID, 42, "ctoggle:2"), data_dir)
        store = Store(data_dir)
        subs = store.get_subscriptions(CHAT_ID)
        store.close()
        assert "Bauausschuss" in subs
        mock_answer.assert_called_once_with("cq1", "✅ Ausschuss abonniert")
        mock_edit.assert_called_once()

    @patch("nwz.bot_commands.edit_message_buttons")
    @patch("nwz.bot_commands.answer_callback_query")
    def test_unsubscribe_via_button(self, mock_answer, mock_edit, data_dir):
        store = Store(data_dir)
        store.subscribe(CHAT_ID, "Bauausschuss")
        store.close()
        handle_callback_query(_make_cq(CHAT_ID, 42, "ctoggle:2"), data_dir)
        store = Store(data_dir)
        subs = store.get_subscriptions(CHAT_ID)
        store.close()
        assert "Bauausschuss" not in subs
        mock_answer.assert_called_once_with("cq1", "❌ Ausschuss gekündigt")

    @patch("nwz.bot_commands.edit_message_buttons")
    @patch("nwz.bot_commands.answer_callback_query")
    def test_answer_and_edit_always_called(self, mock_answer, mock_edit, data_dir):
        handle_callback_query(_make_cq(CHAT_ID, 42, "ctoggle:1"), data_dir)
        mock_answer.assert_called_once()
        mock_edit.assert_called_once()

    @patch("nwz.bot_commands.edit_message_buttons")
    @patch("nwz.bot_commands.answer_callback_query")
    def test_buttons_updated_after_toggle(self, mock_answer, mock_edit, data_dir):
        handle_callback_query(_make_cq(CHAT_ID, 42, "ctoggle:1"), data_dir)
        _chat_id, _msg_id, new_buttons = mock_edit.call_args[0]
        flat = [b for row in new_buttons for b in row]
        # After subscribing idx 1, its button should show ✅
        assert flat[0]["text"] == "✅ 1"

    @patch("nwz.bot_commands.answer_callback_query")
    def test_unauthorized_user(self, mock_answer, tmp_path, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "testtoken")
        nwz_path = tmp_path / "nwz.sqlite"
        Store(nwz_path).close()  # create schema, no users
        handle_callback_query(_make_cq(99999, 42, "ctoggle:1"), nwz_path)
        mock_answer.assert_called_once_with("cq1", "Nicht autorisiert.")

    @patch("nwz.bot_commands.edit_message_buttons")
    @patch("nwz.bot_commands.answer_callback_query")
    def test_legacy_name_based_callback_data(self, mock_answer, mock_edit, data_dir):
        # Old messages sent ctoggle:{name} — must still work
        handle_callback_query(_make_cq(CHAT_ID, 42, "ctoggle:Bauausschuss"), data_dir)
        store = Store(data_dir)
        subs = store.get_subscriptions(CHAT_ID)
        store.close()
        assert "Bauausschuss" in subs

    @patch("nwz.bot_commands.answer_callback_query")
    def test_out_of_range_index(self, mock_answer, data_dir):
        handle_callback_query(_make_cq(CHAT_ID, 42, "ctoggle:99"), data_dir)
        mock_answer.assert_called_once_with("cq1", "Ungültiger Ausschuss.")
