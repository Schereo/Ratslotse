"""Unit tests for the APNs environment fallback in nwz.push.

Xcode debug builds register *sandbox* device tokens, TestFlight/App-Store builds
*production* ones. The server can't tell them apart, so _send_apns retries a
BadDeviceToken once against the other gateway — these tests pin that routing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nwz import push  # noqa: E402

PROD, SBX = push.APNS_PROD_HOST, push.APNS_SANDBOX_HOST


class FakeResp:
    def __init__(self, status_code: int, reason: str = ""):
        self.status_code = status_code
        self._reason = reason

    def json(self):
        if not self._reason:
            raise ValueError("no body")
        return {"reason": self._reason}


class FakeClient:
    """Queued responses per gateway host; records which hosts were hit."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[str] = []

    def post(self, url, headers=None, json=None):
        host = url.split("/3/device/")[0]
        self.calls.append(host)
        return self.responses[host].pop(0)


@pytest.fixture(autouse=True)
def apns_env(monkeypatch):
    monkeypatch.setenv("APNS_TOPIC", "de.ratslotse.app")
    monkeypatch.delenv("APNS_USE_SANDBOX", raising=False)
    # No real .p8 in tests — signing is covered by using the key on the server.
    monkeypatch.setattr(push, "_apns_jwt", lambda: "h.p.s")


def test_prod_token_delivers_without_fallback():
    client = FakeClient({PROD: [FakeResp(200)]})
    assert push._send_apns(client, ["tok"], "t", "b", {}) == []
    assert client.calls == [PROD]


def test_sandbox_token_falls_back_and_delivers():
    """Xcode-Debug-Build (Sandbox-Token), Server-Default Produktion."""
    client = FakeClient({PROD: [FakeResp(400, "BadDeviceToken")], SBX: [FakeResp(200)]})
    assert push._send_apns(client, ["tok"], "t", "b", {}) == []
    assert client.calls == [PROD, SBX]


def test_garbage_token_rejected_by_both_is_pruned():
    client = FakeClient(
        {PROD: [FakeResp(400, "BadDeviceToken")], SBX: [FakeResp(400, "BadDeviceToken")]}
    )
    assert push._send_apns(client, ["tok"], "t", "b", {}) == ["tok"]


def test_unregistered_is_pruned_without_fallback():
    """410/Unregistered heißt: richtiges Env, Token abgelaufen — kein Retry."""
    client = FakeClient({PROD: [FakeResp(410, "Unregistered")]})
    assert push._send_apns(client, ["tok"], "t", "b", {}) == ["tok"]
    assert client.calls == [PROD]


def test_env_restricted_key_falls_back_and_delivers():
    """Portal-beschränkter .p8-Key (nur Sandbox): Prod lehnt den Provider-JWT
    mit 403 BadEnvironmentKeyInToken ab — Zustellung über das andere Gateway."""
    client = FakeClient(
        {PROD: [FakeResp(403, "BadEnvironmentKeyInToken")], SBX: [FakeResp(200)]}
    )
    assert push._send_apns(client, ["tok"], "t", "b", {}) == []
    assert client.calls == [PROD, SBX]


def test_use_sandbox_flips_primary_gateway(monkeypatch):
    monkeypatch.setenv("APNS_USE_SANDBOX", "1")
    client = FakeClient({SBX: [FakeResp(200)]})
    assert push._send_apns(client, ["tok"], "t", "b", {}) == []
    assert client.calls == [SBX]


def test_other_errors_are_kept_not_pruned():
    """5xx/Sonstiges: loggen, Token behalten (transient)."""
    client = FakeClient({PROD: [FakeResp(503)]})
    assert push._send_apns(client, ["tok"], "t", "b", {}) == []
