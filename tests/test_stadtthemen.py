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
    """Attrappe des Rats-Stores — nur, was die Zählung liest. Bloße Texte
    bekommen fortlaufende Kennungen und ein junges Datum."""
    def __init__(self, texte, gespeichert=None):
        jung = (date.today() - timedelta(days=20)).isoformat()
        self.texte = [t if isinstance(t, tuple) else (i, jung, t)
                      for i, t in enumerate(texte, start=1)]
        self.gespeichert = gespeichert or {}
    def decision_texts_dated(self): return self.texte
    def city_topic_decisions(self): return self.gespeichert


def test_schwelle_laesst_duenne_themen_weg():
    texte = ["Radweg"] * city_topics.MIN_DECISIONS + ["Kita"] * (city_topics.MIN_DECISIONS - 1)
    out = city_topics.city_topic_suggestions(_Zaehlgut(texte))
    assert [e["key"] for e in out] == ["cycling"]
    assert out[0]["n"] == city_topics.MIN_DECISIONS
    assert out[0]["months"] == 12
    assert out[0]["name"] == "Radverkehr" and out[0]["description"] and out[0]["context"]


def test_reihenfolge_ist_gemischt_nicht_nach_zahl():
    """Angezeigt wird nach ``ANZEIGE``, nicht nach Zahl: Nach Zahl stünden
    Schulen und Bauthemen vorn, und genau die Einseitigkeit sollte weg."""
    texte = ["Radweg"] * 8 + ["Kita"] * 12 + ["Schwimmbad"] * 9
    keys = [e["key"] for e in city_topics.city_topic_suggestions(_Zaehlgut(texte))]
    assert keys == ["cycling", "pools", "childcare"]


def test_anzeige_nennt_jedes_thema_genau_einmal():
    """Ein Thema ohne Platz in ``ANZEIGE`` landete am Ende, ein Schlüssel, den
    es nicht gibt, stünde dort für immer — beides meldet dieser Test."""
    keys = [t.key for t in city_topics.CITY_TOPICS]
    assert sorted(city_topics.ANZEIGE) == sorted(keys)
    assert len(city_topics.ANZEIGE) == len(set(city_topics.ANZEIGE))


def test_neue_muster_treffen_und_irren_nicht():
    n = city_topics.count_topics([
        "Sanierung der Sporthalle Eversten", "Hallenbad Bümmerstede", "Staatstheater Oldenburg",
        "Feuerwehr Eversten: Anbau", "Wiedervernässung Ipweger Moor", "Brücke am Hafen",
        "Fliegerhorst Oldenburg Grundwasser", "Abfallwirtschaft Satzung",
    ])
    assert (n["sports"], n["pools"], n["culture"], n["fire"]) == (1, 1, 1, 1)
    assert (n["roads"], n["airfield"], n["waste"]) == (1, 1, 1)


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


def test_themen_liste_nennt_das_bild_nur_fuer_kuratierte_themen(client):
    """Das Bild auf der Themen-Karte hängt an ``image_key``: gesetzt für ein Thema,
    das so heißt wie ein Stadtthema, sonst ``None`` — ein selbst getipptes
    „Schulwegsicherheit" darf das Schulen-Bild nicht bekommen."""
    _register(client)
    for name in ("Radverkehr", "Schulwegsicherheit"):
        r = client.post("/api/topics", json={"name": name, "description": "Beschreibung, lang genug."})
        assert r.status_code == 201, r.text
    bilder = {t["name"]: t["image_key"] for t in client.get("/api/topics").json()}
    assert bilder == {"Radverkehr": "cycling", "Schulwegsicherheit": None}
    assert city_topics.bild_key(" radverkehr ") == "cycling"
    assert city_topics.bild_key(None) is None


# --- Eine Liste je Stadtthema (Tims Befund 08.11.2026) -----------------------
#
# Die Kachel im Assistenten zählte per Wortsuche (Theater 18), das Thema bekam
# danach den semantischen Abgleich (35 bzw. 2 seit 2018), und jeder Klick
# wartete auf den Cross-Encoder. Jetzt lesen Kachel, Anlegen, „anpassen" und
# der Wochenlauf dieselbe Liste: ``city_topics.treffer``.

def _rad():
    return next(t for t in city_topics.CITY_TOPICS if t.key == "cycling")


def test_muster_score_ist_die_relevanzschwelle():
    """Als Zahl gesetzt, damit der Router beim Start nicht ``topic_intel``
    (und damit das openai-SDK) lädt — gleich bleiben müssen beide trotzdem."""
    assert city_topics.MUSTER_SCORE == topic_intel.SCHWELLE


def test_zu_thema_erkennt_nur_das_unveraenderte_stadtthema():
    rad = _rad()
    assert city_topics.zu_thema("Radverkehr", rad.description) is rad
    # Leerraum und Groß-/Kleinschreibung des Namens machen kein neues Thema.
    assert city_topics.zu_thema("  radverkehr ", rad.description.replace(" ", "\n", 1)) is rad
    # Eine geänderte Beschreibung schon: Dann gelten Modell und Vagheits-Prüfung.
    assert city_topics.zu_thema("Radverkehr", rad.description + " Auch Lastenräder.") is None
    assert city_topics.zu_thema("Radwege", rad.description) is None
    assert city_topics.zu_thema("Radverkehr", None) is None


def test_treffer_vereint_gespeicherte_liste_und_muster_neueste_zuerst():
    texte = [(1, "2026-01-10", "Neuer Radweg am Hafen"), (2, "2026-03-01", "Haushalt 2026"),
             (3, "2025-06-01", "Fahrradstraße Ofener Straße")]
    # Nr. 2 trifft das Muster nicht — der semantische Abgleich des Wochenlaufs
    # hat sie gefunden, und sie behält ihren Score.
    gespeichert = {"cycling": [(2, 3.5, "2026-03-01")]}
    liste = city_topics.treffer(_Zaehlgut(texte, gespeichert), _rad())
    assert [d for d, _, _ in liste] == [2, 1, 3]
    assert {d: s for d, s, _ in liste} == {2: 3.5, 1: city_topics.MUSTER_SCORE,
                                           3: city_topics.MUSTER_SCORE}


def test_kachel_zaehlt_dieselbe_liste_im_zwoelf_monats_fenster():
    jung = (date.today() - timedelta(days=20)).isoformat()
    alt = (date.today() - timedelta(days=400)).isoformat()
    texte = [(i, jung, "Radweg") for i in range(1, 7)] + [(99, alt, "Radweg")]
    gespeichert = {"cycling": [(50, 2.0, jung)]}
    out = city_topics.city_topic_suggestions(_Zaehlgut(texte, gespeichert))
    # Sechs Mustertreffer plus der semantische, ohne den von vor 400 Tagen.
    assert out[0]["key"] == "cycling" and out[0]["n"] == 7


def _darf_nicht(*_a, **_k):
    raise AssertionError("Ein Stadtthema darf kein Modell rufen")


def test_stadtthema_legt_ohne_modell_mit_der_zahl_der_kachel_an(client, monkeypatch):
    _saat_stadtthema(city_topics.MIN_DECISIONS)
    _register(client)
    monkeypatch.setattr(topic_intel, "treffer", _darf_nicht)
    rad = _rad()
    r = client.post("/api/topics", json={"name": rad.name, "description": rad.description})
    assert r.status_code == 201, r.text
    body = r.json()
    kachel = client.get("/api/topics/suggestions?citywide=0").json()["city"][0]["n"]
    assert body["matched"] and not body["decision_count_capped"]
    assert body["decision_count"] == kachel == city_topics.MIN_DECISIONS
    # „Deine Themen" zählt dasselbe Fenster wie die Kachel.
    assert client.get("/api/topics").json()[0]["hits_12m"] == kachel


def test_describe_fuer_ein_stadtthema_ohne_modell_und_ohne_vagheitswarnung(client, monkeypatch):
    _saat_stadtthema(city_topics.MIN_DECISIONS)
    _register(client)
    monkeypatch.setattr(topic_intel, "analyse", _darf_nicht)
    monkeypatch.setattr(topic_intel, "check_vagueness", _darf_nicht)
    rad = _rad()
    r = client.post("/api/topics/describe", json={"name": rad.name, "description": rad.description})
    assert r.status_code == 200, r.text
    b = r.json()
    assert (b["verdict"], b["vague"], b["parts"]) == ("belegt", False, [])
    assert b["matches"] == b["matches_12m"] == city_topics.MIN_DECISIONS
    assert len(b["examples"]) == 2 and all(e.startswith("Neuer Radweg") for e in b["examples"])


def test_geaenderte_beschreibung_prueft_wie_jedes_eigene_thema(client, monkeypatch):
    _register(client)
    monkeypatch.setattr(topic_intel, "analyse", lambda *a, **k: {
        "description": "x", "matches": 3, "matches_capped": False, "examples": [],
        "verdict": "belegt", "is_council_topic": True, "reason": ""})
    monkeypatch.setattr(topic_intel, "check_vagueness",
                        lambda *a, **k: {"vague": True, "hint": "breit", "suggestion": ""})
    r = client.post("/api/topics/describe",
                    json={"name": "Radverkehr", "description": _rad().description + " Und Lastenräder."})
    assert r.status_code == 200, r.text
    assert r.json()["vague"] is True and "matches_12m" not in r.json()


def test_wochenlauf_gibt_dem_stadtthema_die_liste_seiner_kachel(client, monkeypatch):
    """Der Wochenlauf schreibt die Liste neu und gleicht danach die Themen ab —
    ein Stadtthema darf dabei nicht auf den Cross-Encoder zurückfallen, sonst
    hieße es nach dem Anlegen „6" und am Sonntag etwas anderes."""
    from scripts import match_topics_decisions as lauf

    _saat_stadtthema(city_topics.MIN_DECISIONS)
    _register(client)
    rad = _rad()
    assert client.post("/api/topics", json={"name": rad.name, "description": rad.description}).status_code == 201
    monkeypatch.setattr(lauf, "RATSLOTSE_DB", Path(_pfade()[0]))
    monkeypatch.setattr(lauf, "COUNCIL_DB", Path(_pfade()[1]))
    # Der semantische Teil braucht den Cross-Encoder; hier steht er für „nichts
    # Zusätzliches gefunden".
    monkeypatch.setattr(topic_intel, "treffer", lambda *a, **k: ([], False, 0))
    monkeypatch.setattr(lauf, "treffer", _darf_nicht)
    ergebnis = lauf.process()
    assert ergebnis["stadtthemen_treffer"] >= city_topics.MIN_DECISIONS
    assert ergebnis["matches"] == city_topics.MIN_DECISIONS
