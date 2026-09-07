"""``GET /api/admin/live-probe`` — der O1-Stream als Transkript im Admin-Panel
(Streaming gemockt: kein ffmpeg, kein Gladia)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))
# Wegwerf-Datenbanken und die übrigen Testwerte kommen aus
# `tests/conftest.py` — dort EINMAL je Prozess gesetzt, damit sie nicht an
# der Import-Reihenfolge der Module hängen (siehe die Begründung dort).

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app.deps import require_active  # noqa: E402
from app.routers import admin as admin_router  # noqa: E402
from council import stream_stt  # noqa: E402

ADMIN = {"id": 1, "role": "admin", "roles": ["admin"], "status": "active"}


def _frames(text: str) -> list[dict]:
    return [json.loads(chunk[len("data: "):]) for chunk in text.split("\n\n")
            if chunk.startswith("data: ")]


def test_live_probe_streams_segments_then_done(monkeypatch):
    app.dependency_overrides[require_active] = lambda: ADMIN
    monkeypatch.setattr(stream_stt, "API_KEY", "geheim")

    def fake_record(on_segment=None, max_seconds=None, people=None, stop=None, **kw):
        on_segment(0.5, 2.2, "Wir kommen zu Punkt 6.1.")
        on_segment(3.0, 5.1, "Frau Drügemöller, bitte.")
        return [(0.5, "…"), (3.0, "…")]

    monkeypatch.setattr(stream_stt, "record_and_transcribe", fake_record)
    try:
        r = TestClient(app).get("/api/admin/live-probe?seconds=30")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        frames = _frames(r.text)
        assert [f["type"] for f in frames] == ["status", "segment", "segment", "done"]
        assert frames[1]["text"] == "Wir kommen zu Punkt 6.1." and frames[1]["end"] == 2.2
        assert "wall" in frames[1]
        assert frames[3]["segments"] == 2
        # Die Sperre ist nach dem Ende wieder frei.
        assert admin_router._LIVE_PROBE_LOCK.acquire(blocking=False)
        admin_router._LIVE_PROBE_LOCK.release()
    finally:
        app.dependency_overrides.pop(require_active, None)


def test_live_probe_needs_key_and_admin(monkeypatch):
    monkeypatch.setattr(stream_stt, "API_KEY", "")
    app.dependency_overrides[require_active] = lambda: ADMIN
    try:
        assert TestClient(app).get("/api/admin/live-probe").status_code == 503
    finally:
        app.dependency_overrides.pop(require_active, None)
    app.dependency_overrides[require_active] = lambda: {"id": 2, "role": "user", "roles": [], "status": "active"}
    try:
        monkeypatch.setattr(stream_stt, "API_KEY", "geheim")
        assert TestClient(app).get("/api/admin/live-probe").status_code == 403
    finally:
        app.dependency_overrides.pop(require_active, None)


def test_live_probe_reports_a_failed_stream(monkeypatch):
    app.dependency_overrides[require_active] = lambda: ADMIN
    monkeypatch.setattr(stream_stt, "API_KEY", "geheim")
    monkeypatch.setattr(stream_stt, "record_and_transcribe",
                        mock.Mock(side_effect=stream_stt.StreamUnavailable("Sitzung nicht eröffnet")))
    try:
        frames = _frames(TestClient(app).get("/api/admin/live-probe?seconds=30").text)
        assert frames[-1]["type"] == "error" and "nicht eröffnet" in frames[-1]["message"]
    finally:
        app.dependency_overrides.pop(require_active, None)
