"""Kuratierte Stadtthemen im Vorschlags-Endpunkt (Onboarding, Schritt 3).

Radverkehr, Kitas, Wohnungsbau statt Straßennamen — und nichts davon ohne
Substanz: Ein Thema steht nur da, wenn der Rat in den letzten zwölf Monaten
mindestens ``MIN_DECISIONS`` Mal dazu entschieden hat.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))

from council import city_topics, topic_intel  # noqa: E402
from tests.test_backend_api import CouncilSession, CouncilStore, _register, app  # noqa: E402
from tests.test_stadtteil_vorschlaege import _pfade, _saat  # noqa: E402


@pytest.fixture(autouse=True)
def frische_dbs():
    for basis in _pfade():
        for endung in ("", "-wal", "-shm"):
            Path(basis + endung).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


# --- Registry -----------------------------------------------------------------

def test_registry_ist_sauber():
    """Schlüssel eindeutig, Muster übersetzbar, Namen keine Anweisungen —
    die Struktur-Prüfung von ``add_topic`` gilt auch für das, was wir selbst
    vorschlagen. Gattungswörter („Schulen") sind hier dagegen erlaubt: Das
    Gattungswort IST das Interesse, der Vorfilter ``looks_generic`` gilt nur
    für Entitäten."""
    keys = [t.key for t in city_topics.CITY_TOPICS]
    assert len(keys) == len(set(keys))
    for t in city_topics.CITY_TOPICS:
        assert t.key.isidentifier() and t.key.islower(), t.key
        assert not topic_intel.looks_like_instruction(t.name), t.name
        assert 60 <= len(t.description) <= 300, t.name
        assert t.context


def test_zaehlung_je_text_einmal():
    texte = ["Neuer Radweg und Fahrradstraße am Radweg", "Kita-Ausbau", "Haushalt 2026"]
    n = city_topics.count_topics(texte)
    assert n["cycling"] == 1          # ein Text, ein Treffer — nicht drei
    assert n["childcare"] == 1
    assert n["housing"] == 0


def test_schul_muster_trifft_keine_schulden_und_hochschulen():
    n = city_topics.count_topics(["Schuldenstand der Stadt", "Hochschule Emden/Leer",
                                  "Fachschule für Sozialpädagogik", "Grundschule Wechloy"])
    assert n["schools"] == 1


def test_baum_muster_trifft_keine_baumassnahme_und_kein_parken():
    n = city_topics.count_topics(["Baumaßnahme Rathaus", "Parkplatz am Bahnhof",
                                  "Baumschutzsatzung", "Bäume am Schlossgarten"])
    assert n["green"] == 2


class _Zaehlgut:
    def __init__(self, texte): self.texte = texte
    def decision_texts_since(self, date_from): return self.texte


def test_schwelle_laesst_duenne_themen_weg():
    texte = ["Radweg"] * city_topics.MIN_DECISIONS + ["Kita"] * (city_topics.MIN_DECISIONS - 1)
    out = city_topics.city_topic_suggestions(_Zaehlgut(texte))
    assert [e["key"] for e in out] == ["cycling"]
    assert out[0]["n"] == city_topics.MIN_DECISIONS
    assert out[0]["months"] == 12
    assert out[0]["name"] == "Radverkehr" and out[0]["description"] and out[0]["context"]


def test_aktivste_zuerst():
    texte = ["Radweg"] * 8 + ["Kita"] * 12
    assert [e["key"] for e in city_topics.city_topic_suggestions(_Zaehlgut(texte))] == ["childcare", "cycling"]


# --- Endpunkt -----------------------------------------------------------------

def _saat_stadtthema(anzahl: int, titel: str = "Neuer Radweg") -> None:
    council = CouncilStore(Path(_pfade()[1]))
    jung = (date.today() - timedelta(days=20)).isoformat()
    council.save_session(CouncilSession(7, "Rat", jung, "17:00", "Ratssaal"))
    with council._conn:
        for i in range(anzahl):
            council._insert_decision(7, i, "decision", None, f"Ö {i}", f"{titel} {i}", "B",
                                     "accepted", None, None, None, [], None, None, None)
    council.close()


def test_stadtthemen_stehen_in_der_antwort(client):
    _saat_stadtthema(city_topics.MIN_DECISIONS)
    _register(client)
    r = client.get("/api/topics/suggestions")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "city" in body and "suggestions" in body and "districts" in body
    assert [e["key"] for e in body["city"]] == ["cycling"]
    eintrag = body["city"][0]
    assert eintrag["name"] == "Radverkehr"
    assert eintrag["n"] == city_topics.MIN_DECISIONS and eintrag["months"] == 12
    # Die Form ist die der Entitäts-Vorschläge plus Schlüssel und Zeitraum —
    # was hier fehlt, schneidet FastAPI still ab.
    assert set(eintrag) == {"key", "name", "description", "context", "n", "months"}


def test_stadtthemen_bleiben_auch_wenn_angelegt(client):
    """Anders als die Entitäten wird die Liste NICHT um eigene Themen
    bereinigt: Sie ist stabil, die Oberfläche markiert das Angelegte."""
    _saat_stadtthema(city_topics.MIN_DECISIONS)
    _register(client)
    r = client.post("/api/topics", json={"name": "Radverkehr", "description": "Radwege in Oldenburg."})
    assert r.status_code == 201, r.text
    assert [e["key"] for e in client.get("/api/topics/suggestions").json()["city"]] == ["cycling"]


def test_city_0_laesst_stadtthemen_weg(client):
    _saat_stadtthema(city_topics.MIN_DECISIONS)
    _register(client)
    assert client.get("/api/topics/suggestions?city=0").json()["city"] == []


def test_limit_und_nearby_je_stadtteil(client):
    """Der Assistent fragt zwei je Stadtteil ohne Nachbarschaft: Vier
    Stadtteile mit je sechs Chips plus nebenan waren eine Wand."""
    _saat()
    _register(client)
    r = client.get("/api/topics/suggestions?district=osternburg&citywide=0&city=0&limit=2&nearby=0")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["city"] == [] and body["suggestions"] == []
    (gruppe,) = body["districts"]
    assert len(gruppe["suggestions"]) <= 2
    assert gruppe["nearby"] == []


def test_limit_ausser_bereich(client):
    _register(client)
    assert client.get("/api/topics/suggestions?limit=0").status_code == 422
    assert client.get("/api/topics/suggestions?limit=7").status_code == 422
