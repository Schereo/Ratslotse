"""Cron-Alerting: notify_admin loggt immer und mailt best-effort."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from nwz import alerts


def test_notify_admin_without_recipient_only_logs(monkeypatch, caplog):
    monkeypatch.delenv("ALERT_EMAIL", raising=False)
    monkeypatch.delenv("WEB_ADMIN_EMAIL", raising=False)
    with patch("nwz.email.send_email") as send:
        alerts.notify_admin("kaputt")
    send.assert_not_called()


def test_notify_admin_emails_recipient(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL", "ops@test.de")
    monkeypatch.setenv("RESEND_API_KEY", "x")
    with patch("nwz.email.send_email", return_value="id") as send:
        alerts.notify_admin("⚠️ Cron <b>backup_db</b> ist fehlgeschlagen")
    assert send.call_count == 1
    args, kwargs = send.call_args
    assert args[0] == "ops@test.de"
    assert "Cron-Alarm" in args[1]
    # Plain-Text-Teil ist HTML-frei
    assert "<b>" not in kwargs["text"]


def test_notify_admin_falls_back_to_web_admin_email(monkeypatch):
    monkeypatch.delenv("ALERT_EMAIL", raising=False)
    monkeypatch.setenv("WEB_ADMIN_EMAIL", "admin@test.de")
    monkeypatch.setenv("RESEND_API_KEY", "x")
    with patch("nwz.email.send_email", return_value="id") as send:
        alerts.notify_admin("kaputt")
    assert send.call_args[0][0] == "admin@test.de"


def test_notify_admin_never_raises_on_send_failure(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL", "ops@test.de")
    monkeypatch.setenv("RESEND_API_KEY", "x")
    with patch("nwz.email.send_email", side_effect=RuntimeError("resend down")):
        alerts.notify_admin("kaputt")  # darf nicht raisen


def test_run_guarded_alerts_and_reraises(monkeypatch):
    monkeypatch.delenv("ALERT_EMAIL", raising=False)
    monkeypatch.delenv("WEB_ADMIN_EMAIL", raising=False)

    def boom() -> None:
        raise ValueError("kaputt")

    with patch.object(alerts, "notify_admin") as notify:
        with pytest.raises(ValueError):
            alerts.run_guarded("testjob", boom)
    assert notify.call_count == 1
    assert "testjob" in notify.call_args[0][0]
