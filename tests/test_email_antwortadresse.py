"""Antworten auf Ratslotse-Mails landen bei einer echten Adresse, nicht bei noreply@."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kern import email  # noqa: E402


class _Antwort:
    def raise_for_status(self):
        return None

    def json(self):
        return {"id": "x"}


def _gesendet(monkeypatch, **kwargs):
    gesehen = {}
    monkeypatch.setenv("RESEND_API_KEY", "k")
    monkeypatch.setattr(email.requests, "post", lambda url, headers, json, timeout: (gesehen.update(json), _Antwort())[1])
    email.send_email("a@example.org", "Betreff", "<p>x</p>", **kwargs)
    return gesehen


def test_ohne_eintrag_keine_antwortadresse(monkeypatch):
    monkeypatch.delenv("EMAIL_REPLY_TO", raising=False)
    assert "reply_to" not in _gesendet(monkeypatch)


def test_die_antwortadresse_aus_der_env_gilt_fuer_jede_mail(monkeypatch):
    monkeypatch.setenv("EMAIL_REPLY_TO", "antwort@example.org")
    assert _gesendet(monkeypatch)["reply_to"] == "antwort@example.org"


def test_eine_eigene_antwortadresse_gewinnt(monkeypatch):
    monkeypatch.setenv("EMAIL_REPLY_TO", "antwort@example.org")
    assert _gesendet(monkeypatch, reply_to="person@example.org")["reply_to"] == "person@example.org"
