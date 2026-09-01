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
os.environ["RATSLOTSE_DB"] = str(Path(_TMP) / "ratslotse.sqlite")
os.environ["COUNCIL_DB"] = str(Path(_TMP) / "council.sqlite")
os.environ["WEB_JWT_SECRET"] = "test-secret"
os.environ["COOKIE_SECURE"] = "false"
os.environ["DISABLE_RATE_LIMIT"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.deps import get_council_store  # noqa: E402
from council.store import CouncilStore  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def council_store(tmp_path):
    """Eigene Wegwerf-Council-DB je Test, über dieselbe Dependency
    verdrahtet, die die App auch für echte Requests benutzt — die neuen
    Endpunkte greifen auf ``store._conn`` direkt zu, das braucht echtes
    Schema statt Mocks."""
    store = CouncilStore(tmp_path / "council-test.sqlite")
    app.dependency_overrides[get_council_store] = lambda: store
    try:
        yield store
    finally:
        del app.dependency_overrides[get_council_store]
        store.close()


def _mit_token(monkeypatch, token="geheim-fuer-den-bot"):
    get_settings.cache_clear()
    monkeypatch.setenv("SOCIAL_API_TOKEN", token)
    return token


def test_ohne_token_ist_die_schnittstelle_aus(client):
    """Eine Standard-Installation soll gar nichts exponieren — und nicht
    verraten, dass es den Endpunkt gäbe."""
    get_settings.cache_clear()
    assert client.get("/api/social/week-preview").status_code == 404


def test_falscher_token_wird_abgewiesen(client, monkeypatch):
    _mit_token(monkeypatch)
    try:
        r = client.get("/api/social/week-preview",
                       headers={"X-Social-Token": "falsch"})
        assert r.status_code == 401
    finally:
        get_settings.cache_clear()


def test_richtiger_token_liefert_die_vorschau(client, monkeypatch):
    token = _mit_token(monkeypatch)
    try:
        r = client.get("/api/social/week-preview",
                       headers={"X-Social-Token": token})
        assert r.status_code == 200
        daten = r.json()
        assert "sessions" in daten and "items" in daten and "upcoming" in daten
    finally:
        get_settings.cache_clear()


def test_nur_jpeg_wird_angenommen(client, monkeypatch, tmp_path):
    """Die Endung sagt nichts — geprüft werden die Magic Bytes."""
    token = _mit_token(monkeypatch)
    monkeypatch.setenv("SOCIAL_MEDIA_DIR", str(tmp_path))
    try:
        r = client.post(
            "/api/social/media/2026-08-24",
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
            "/api/social/media/..%2F..%2Fetc",
            headers={"X-Social-Token": token},
            files={"dateien": ("a.jpg", io.BytesIO(b"\xff\xd8\xffrest"), "image/jpeg")},
        )
        assert r.status_code in (400, 404)
    finally:
        get_settings.cache_clear()


def test_sitzungen_tag_muss_datum_sein(client, monkeypatch):
    token = _mit_token(monkeypatch)
    try:
        r = client.get("/api/social/sessions/nicht-date",
                       headers={"X-Social-Token": token})
        assert r.status_code == 400
    finally:
        get_settings.cache_clear()


def test_sitzungen_liefert_den_kalendertag(client, monkeypatch, council_store):
    token = _mit_token(monkeypatch)
    council_store._conn.execute(
        "INSERT INTO council_sessions (ksinr, committee, session_date, "
        "session_time, location, fetched_at) VALUES "
        "(1, 'Verkehrsausschuss', '2026-08-24', '17:00', 'Ratssaal', '')")
    council_store._conn.commit()
    try:
        r = client.get("/api/social/sessions/2026-08-24",
                       headers={"X-Social-Token": token})
        assert r.status_code == 200
        daten = r.json()
        assert len(daten) == 1 and daten[0]["committee"] == "Verkehrsausschuss"
    finally:
        get_settings.cache_clear()


def test_fundstueck_ohne_eintrag_ist_null(client, monkeypatch, council_store):
    token = _mit_token(monkeypatch)
    try:
        r = client.get("/api/social/daily-find/2026-08-25",
                       headers={"X-Social-Token": token})
        assert r.status_code == 200 and r.json() is None
    finally:
        get_settings.cache_clear()


def test_neue_beschluesse_filtert_wichtigkeit_und_id(client, monkeypatch, council_store):
    token = _mit_token(monkeypatch)
    c = council_store._conn
    c.execute("INSERT INTO council_sessions (ksinr, committee, session_date, "
              "session_time, location, fetched_at) VALUES "
              "(1, 'Rat', '2026-08-24', '18:00', 'Ratssaal', '')")
    for bid, wichtig in ((10, 80), (11, 10)):  # zweiter liegt unter der Schwelle
        c.execute(
            "INSERT INTO council_decisions (id, ksinr, position, kind, title, "
            "outcome, vote, importance) VALUES (?, 1, 1, 'decision', "
            "'Beschluss ' || ?, 'accepted', 'majority', ?)",
            (bid, bid, wichtig))
    c.execute("INSERT INTO council_decision_votes (decision_id, faction, stance) "
              "VALUES (10, 'CDU', 'against')")
    c.commit()
    try:
        r = client.get("/api/social/new-decisions",
                       headers={"X-Social-Token": token},
                       params={"seit_id": 0, "mindest_wichtig": 55})
        assert r.status_code == 200
        daten = r.json()
        assert [d["id"] for d in daten] == [10]          # 11 fällt durch die Schwelle
        assert daten[0]["votes"] == [{"faction": "CDU", "stance": "against"}]
    finally:
        get_settings.cache_clear()


def test_hoechste_beschluss_id_ohne_bestand_ist_null(client, monkeypatch, council_store):
    token = _mit_token(monkeypatch)
    try:
        r = client.get("/api/social/highest-decision-id",
                       headers={"X-Social-Token": token})
        assert r.status_code == 200 and r.json() == {"highest_id": 0}
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
            "/api/social/media/2026-08-24",
            headers={"X-Social-Token": token},
            files=[("dateien", ("../boese.php", io.BytesIO(jpeg), "image/jpeg")),
                   ("dateien", ("zweite.jpg", io.BytesIO(jpeg), "image/jpeg"))],
        )
        assert r.status_code == 200, r.text
        daten = r.json()
        assert daten["count"] == 2
        assert daten["urls"] == [
            "https://example.org/social/2026-08-24/2026-08-24-01.jpg",
            "https://example.org/social/2026-08-24/2026-08-24-02.jpg",
        ]
        abgelegt = sorted(p.name for p in (tmp_path / "2026-08-24").iterdir())
        assert abgelegt == ["2026-08-24-01.jpg", "2026-08-24-02.jpg"]
    finally:
        get_settings.cache_clear()


def test_kennung_darf_mehr_als_ein_datum_sein(client, monkeypatch, tmp_path):
    """Der Bot legt nicht nur Wochen-Karussells ab, sondern auch
    „2026-08-24-fundstueck", „official_text-4711" und „stories-2026-08-24".
    Das Datumsmuster wies die alle ab."""
    token = _mit_token(monkeypatch)
    monkeypatch.setenv("SOCIAL_MEDIA_DIR", str(tmp_path))
    monkeypatch.setenv("SOCIAL_MEDIA_BASE_URL", "https://example.org/social")
    jpeg = b"\xff\xd8\xff" + b"x" * 64
    try:
        for kennung in ("2026-08-24", "2026-08-24-fundstueck", "beschluss-4711",
                        "stories-2026-08-24"):
            r = client.post(f"/api/social/media/{kennung}",
                            headers={"X-Social-Token": token},
                            files={"dateien": ("k.jpg", io.BytesIO(jpeg), "image/jpeg")})
            assert r.status_code == 200, (kennung, r.text)
            assert r.json()["urls"] == [
                f"https://example.org/social/{kennung}/{kennung}-01.jpg"]
    finally:
        get_settings.cache_clear()


def test_kennung_laesst_keinen_pfad_durch(client, monkeypatch, tmp_path):
    """Weder Schrägstrich noch Punkt noch Großbuchstaben — die Kennung wird
    zu einem Verzeichnisnamen, also bleibt sie ein Wort."""
    token = _mit_token(monkeypatch)
    monkeypatch.setenv("SOCIAL_MEDIA_DIR", str(tmp_path))
    jpeg = b"\xff\xd8\xff" + b"x" * 64
    try:
        for boese in ("stories/2026-08-24", "..", "-start", "a" * 65, "Gross"):
            r = client.post(f"/api/social/media/{boese}",
                            headers={"X-Social-Token": token},
                            files={"dateien": ("k.jpg", io.BytesIO(jpeg), "image/jpeg")})
            assert r.status_code in (400, 404), (boese, r.status_code)
    finally:
        get_settings.cache_clear()


def test_abgelegte_bilder_sind_oeffentlich_abrufbar(monkeypatch, tmp_path):
    """Der Upload allein nützt nichts: Instagram holt jedes Bild SELBST von
    einer öffentlichen Adresse. Bis zum 19.08.26 landeten die Dateien im
    public/ des Frontends — Next.js liest das aber beim Build und lieferte
    später hinzugefügte Dateien nie aus (Upload ok, URL 404)."""
    get_settings.cache_clear()
    monkeypatch.setenv("SOCIAL_API_TOKEN", "geheim-fuer-den-bot")
    monkeypatch.setenv("SOCIAL_MEDIA_DIR", str(tmp_path))
    monkeypatch.setenv("SOCIAL_MEDIA_BASE_URL", "https://example.org/api/social-media")
    try:
        # Die Einhängung passiert beim Import — für den Test frisch aufbauen.
        import importlib
        import app.main as hauptmodul
        modul = importlib.reload(hauptmodul)
        with TestClient(modul.app) as c:
            jpeg = b"\xff\xd8\xff" + b"y" * 200
            r = c.post("/api/social/media/2026-08-24",
                       headers={"X-Social-Token": "geheim-fuer-den-bot"},
                       files={"dateien": ("k.jpg", io.BytesIO(jpeg), "image/jpeg")})
            assert r.status_code == 200, r.text
            url = r.json()["urls"][0]
            assert url.startswith("https://example.org/api/social-media/")

            # Und dieselbe Datei kommt OHNE Token wieder heraus.
            pfad = url.split("https://example.org", 1)[1]
            hol = c.get(pfad)
            assert hol.status_code == 200, pfad
            assert hol.content == jpeg
    finally:
        get_settings.cache_clear()
        import importlib
        import app.main as hauptmodul
        importlib.reload(hauptmodul)
