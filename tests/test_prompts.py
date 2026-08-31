"""Die Prompt-Vorlagen aus `kern/prompts.py`.

Seit 08/2026 gibt es keine Overrides mehr — die Vorlagen sind Code. Geprüft
wird deshalb nur noch, was auch als Code schiefgehen kann: dass jede Vorlage
sich mit ihren dokumentierten Platzhaltern füllen lässt, und dass die
JSON-Beispiele darin ihre geschweiften Klammern richtig verdoppeln.
"""
from __future__ import annotations

import pytest

from kern import prompts


def test_defaults_render_with_placeholders():
    # Format prompts must accept their documented placeholders.
    prompts.render("committee_summary_user", committee="C", datum="18.08.2026", items_text="I")
    prompts.render("council_watcher_user", committee="C", session_date="d", items_text="I", topics_text="T")


def test_raw_prompts_have_valid_json_braces():
    # Prompts without placeholders must keep literal JSON braces escaped.
    assert '{"vague": true/false' in prompts.get("vagueness_check_system")


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        prompts.get("does_not_exist")


def test_jede_vorlage_ist_formatierbar():
    """Keine Vorlage darf eine einzelne geschweifte Klammer tragen.

    `render()` ruft `str.format()`; eine unverdoppelte Klammer in einem
    JSON-Beispiel fliegt dort erst zur Laufzeit auf — im Zweifel mitten in
    einem Cron-Lauf. Hier fällt sie sofort auf.
    """
    import string
    kaputt = []
    for key, meta in prompts.DEFAULTS.items():
        try:
            list(string.Formatter().parse(meta["template"]))
        except ValueError as e:
            kaputt.append(f"{key}: {e}")
    assert not kaputt, "Vorlagen mit fehlerhaften Klammern:\n  " + "\n  ".join(kaputt)
