"""Tests for the admin-editable prompt store (nwz/prompts.py)."""
from __future__ import annotations

import pytest

from nwz import prompts


@pytest.fixture
def temp_prompt_db(tmp_path, monkeypatch):
    """Point the prompt store at a throwaway DB so overrides don't touch real data."""
    monkeypatch.setattr(prompts, "_DB_PATH", tmp_path / "nwz.sqlite")
    return tmp_path


def test_defaults_render_with_placeholders(temp_prompt_db):
    # Format prompts must accept their documented placeholders.
    prompts.render("committee_summary_user", committee="C", items_text="I")
    prompts.render("council_watcher_user", committee="C", session_date="d", items_text="I", topics_text="T")


def test_raw_prompts_have_valid_json_braces(temp_prompt_db):
    # Raw prompts are used without .format(); their literal braces must survive.
    assert '{"vague": true/false' in prompts.get("vagueness_check_system")


def test_get_returns_default_when_no_override(temp_prompt_db):
    assert prompts.get("council_watcher_system") == prompts.DEFAULTS["council_watcher_system"]["template"]
    assert prompts.is_overridden("council_watcher_system") is False


def test_set_override_takes_effect(temp_prompt_db):
    prompts.set_content("council_watcher_system", "Neuer Text {session_date}")
    assert prompts.is_overridden("council_watcher_system") is True
    assert prompts.get("council_watcher_system") == "Neuer Text {session_date}"
    assert prompts.render("council_watcher_system", session_date="X") == "Neuer Text X"


def test_reset_restores_default(temp_prompt_db):
    prompts.set_content("council_watcher_system", "X")
    prompts.reset("council_watcher_system")
    assert prompts.is_overridden("council_watcher_system") is False
    assert prompts.get("council_watcher_system") == prompts.DEFAULTS["council_watcher_system"]["template"]


def test_list_all_reports_override_state(temp_prompt_db):
    prompts.set_content("committee_summary_system", "Custom")
    by_key = {p["key"]: p for p in prompts.list_all()}
    assert len(by_key) == len(prompts.DEFAULTS)
    assert by_key["committee_summary_system"]["is_overridden"] is True
    assert by_key["committee_summary_system"]["content"] == "Custom"
    assert by_key["council_watcher_system"]["is_overridden"] is False


def test_unknown_key_raises(temp_prompt_db):
    with pytest.raises(KeyError):
        prompts.get("does_not_exist")
    with pytest.raises(KeyError):
        prompts.set_content("does_not_exist", "x")
