"""Die Bot-Schnittstelle: aus ohne Token, eng beim Hochladen."""
from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Wie in test_backend_api.py: Backend importierbar machen und auf
# Wegwerf-Datenbanken zeigen, BEVOR die App importiert wird.
_BACKEND = Path(__file__).resolve().parents[1] / "web" / "backend"
sys.path.insert(0, str(_BACKEND))
_TMP = tempfile.mkdtemp()
os.environ["NWZ_DB"] = str(Path(_TMP) / "nwz.sqlite")
os.environ["COUNCIL_DB"] = str(Path(_TMP) / "council.sqlite")
os.environ["WEB_JWT_SECRET"] = "test-secret"
os.environ["COOKIE_SECURE"] = "false"
os.environ["DISABLE_RATE_LIMIT"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def _mit_token(monkeypatch, token="geheim-fuer-den-bot"):
    get_settings.cache_clear()
    monkeypatch.setenv("SOCIAL_API_TOKEN", token)
    return token


def test_ohne_token_ist_die_schnittstelle_aus(client):
    """Eine Standard-Installation soll gar nichts exponieren — und nicht
    verraten, dass es den Endpunkt gäbe."""
    get_settings.cache_clear()
    assert client.get("/api/social/wochenvorschau").status_code == 404


def test_falscher_token_wird_abgewiesen(client, monkeypatch):
    _mit_token(monkeypatch)
    try:
        r = client.get("/api/social/wochenvorschau",
                       headers={"X-Social-Token": "falsch"})
        assert r.status_code == 401
    finally:
        get_settings.cache_clear()


def test_richtiger_token_liefert_die_vorschau(client, monkeypatch):
    token = _mit_token(monkeypatch)
    try:
        r = client.get("/api/social/wochenvorschau",
                       headers={"X-Social-Token": token})
        assert r.status_code == 200
        daten = r.json()
        assert "sitzungen" in daten and "punkte" in daten and "kommende" in daten
    finally:
        get_settings.cache_clear()


def test_nur_jpeg_wird_angenommen(client, monkeypatch, tmp_path):
    """Die Endung sagt nichts — geprüft werden die Magic Bytes."""
    token = _mit_token(monkeypatch)
    monkeypatch.setenv("SOCIAL_MEDIA_DIR", str(tmp_path))
    try:
        r = client.post(
            "/api/social/medien/2026-08-24",
            headers={"X-Social-Token": token},
            files={"dateien": ("karte.jpg", io.BytesIO(b"<html>kein Bild"), "image/jpeg")},
        )
        assert r.status_code == 415
    finally:
        get_settings.cache_clear()


def test_tag_muss_ein_datum_sein(client, monkeypatch, tmp_path):
    token = _mit_token(monkeypatch)
    monkeypatch.setenv("SOCIAL_MEDIA_DIR", str(tmp_path))
    try:
        r = client.post(
            "/api/social/medien/..%2F..%2Fetc",
            headers={"X-Social-Token": token},
            files={"dateien": ("a.jpg", io.BytesIO(b"\xff\xd8\xffrest"), "image/jpeg")},
        )
        assert r.status_code in (400, 404)
    finally:
        get_settings.cache_clear()


def test_hochladen_vergibt_die_namen_selbst(client, monkeypatch, tmp_path):
    """Der Aufrufer bestimmt den Inhalt, nicht den Dateinamen."""
    token = _mit_token(monkeypatch)
    monkeypatch.setenv("SOCIAL_MEDIA_DIR", str(tmp_path))
    monkeypatch.setenv("SOCIAL_MEDIA_BASE_URL", "https://example.org/social")
    try:
        jpeg = b"\xff\xd8\xff" + b"x" * 100
        r = client.post(
            "/api/social/medien/2026-08-24",
            headers={"X-Social-Token": token},
            files=[("dateien", ("../boese.php", io.BytesIO(jpeg), "image/jpeg")),
                   ("dateien", ("zweite.jpg", io.BytesIO(jpeg), "image/jpeg"))],
        )
        assert r.status_code == 200, r.text
        daten = r.json()
        assert daten["anzahl"] == 2
        assert daten["urls"] == [
            "https://example.org/social/2026-08-24/2026-08-24-01.jpg",
            "https://example.org/social/2026-08-24/2026-08-24-02.jpg",
        ]
        abgelegt = sorted(p.name for p in (tmp_path / "2026-08-24").iterdir())
        assert abgelegt == ["2026-08-24-01.jpg", "2026-08-24-02.jpg"]
    finally:
        get_settings.cache_clear()
