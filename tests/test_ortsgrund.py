"""Die kurze Erklärung, warum ein Vorschlag an einem Stadtteil hängt.

„Kommunale Wärmeplanung" unter Kreyenbrück las sich wie ein Fehler — bis
„Maßnahme Machbarkeitsstudien" darunter stand (Tim, 03.09.2026). Der Text
kommt aus dem Titel des Beschlusses, der Entität und Ortsbereich verbindet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web" / "backend"))

from tests.test_backend_api import _register, app  # noqa: E402
from tests.test_stadtteil_vorschlaege import _pfade, _saat  # noqa: E402
from app.routers.topics import _ortsgrund  # noqa: E402


@pytest.fixture(autouse=True)
def frische_dbs():
    for basis in _pfade():
        for endung in ("", "-wal", "-shm"):
            Path(basis + endung).unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_name_als_praefix_faellt_weg():
    """Der Fall, für den es die Zeile gibt."""
    assert _ortsgrund("Kommunale Wärmeplanung",
                      "Kommunale Wärmeplanung: Maßnahme Machbarkeitsstudien - Beschluss") \
        == "Maßnahme Machbarkeitsstudien"


def test_name_mitten_im_satz_bleibt_stehen():
    """Herausschneiden zerlegt die Grammatik: „Bebauungsplan 831 () - Prüfung
    der Stellungnahmen" und „Erweiterung der Zügigkeit der" waren am Bestand
    gemessene Ergebnisse der naiven Variante."""
    assert _ortsgrund("Grundschule Wechloy", "Erweiterung der Zügigkeit der Grundschule Wechloy") \
        == "Erweiterung der Zügigkeit der Grundschule Wechloy"
    assert "()" not in (_ortsgrund(
        "Stadion Maastrichter Straße",
        "Bebauungsplan 831 (Stadion Maastrichter Straße) - Prüfung der Stellungnahmen") or "")


def test_verfahrensschwanz_faellt_weg():
    assert _ortsgrund("Sportpark Dornstede", "Umkleidegebäude Sportpark Dornstede - Beschluss") \
        == "Umkleidegebäude Sportpark Dornstede"
    assert _ortsgrund("Altes Gymnasium",
                      "Umbau Altes Gymnasium - Antrag mit mündlichem Bericht der Verwaltung") \
        == "Umbau Altes Gymnasium"


def test_nur_verfahren_ergibt_nichts():
    """„Prüfung der Stellungnahmen und Satzungsbeschluss" erklärt keinen Ortsbezug."""
    assert _ortsgrund("Watertucht", "Watertucht - Prüfung der Stellungnahmen und Satzungsbeschluss") is None


def test_titel_der_mit_einem_verfahrenswort_beginnt_bleibt():
    """Gegenprobe zum vorigen Test: Der Titel FÄNGT mit „Sachstandsbericht" an
    und sagt trotzdem etwas. Genau daran ist die erste, zu strenge Fassung
    gescheitert."""
    assert _ortsgrund("Schlossplatz",
                      "Sachstandsbericht und weiteres Vorgehen Spielbereich Schlossplatz") \
        == "Sachstandsbericht und weiteres Vorgehen Spielbereich Schlossplatz"


def test_herkunftsklammer_mit_personennamen_faellt_ueberall_weg():
    """Sie nennt, WER beantragt hat — und trägt Personennamen. Beim Kürzen auf
    Chip-Länge stand sonst der halbe Name einer Person auf der Karte."""
    grund = _ortsgrund(
        "Heidbrook",
        "Fällungen von Fichten im Heidbrook (beratendes Mitglied Frau Dr. Kreft-Kohlhage "
        "vom 28.03.2026) - Antrag mit mündlichem Bericht der Verwaltung")
    assert grund == "Fällungen von Fichten im Heidbrook"
    assert _ortsgrund("Bolzplatz", "Neuer Bolzplatz (SPD-Fraktion vom 16.02.2026)") \
        == "Neuer Bolzplatz"


def test_reine_wiederholung_des_namens_ergibt_nichts():
    assert _ortsgrund("Alte Fleiwa", "Alte Fleiwa") is None
    assert _ortsgrund("Alte Fleiwa", "Alte Fleiwa - Bericht") is None


def test_lange_titel_werden_an_der_wortgrenze_gekuerzt():
    lang = ("Außerplanmäßige Bewilligung einer Verpflichtungsermächtigung in Höhe von "
            "200.000 Euro für die Beschaffung einer Sandsackfüllmaschine")
    grund = _ortsgrund("Sandsackfüllmaschine", lang)
    assert grund.endswith("…") and len(grund) <= 73
    assert not grund.rstrip("…").endswith(" ")
    assert lang.startswith(grund.rstrip("…"))


def test_leerer_titel():
    assert _ortsgrund("Irgendwas", None) is None
    assert _ortsgrund("Irgendwas", "") is None


def test_endpunkt_liefert_das_feld(client):
    """Pflichtfeld in der Antwortform: Was fehlt, wäre ein 500er — und was nicht
    deklariert ist, schneidet FastAPI still ab."""
    _saat()
    _register(client)
    r = client.get("/api/topics/suggestions?district=osternburg&citywide=0&city=0")
    assert r.status_code == 200, r.text
    (gruppe,) = r.json()["districts"]
    assert gruppe["suggestions"], "ohne Vorschläge prüft der Test nichts"
    for v in gruppe["suggestions"]:
        assert "place_reason" in v
    # Der interne Slug darf NICHT durchrutschen.
    assert "slug" not in gruppe["suggestions"][0]
