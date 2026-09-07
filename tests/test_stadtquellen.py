"""Stadt-Quellen je Viertel: Sperrungen (council/sperrungen.py) und der
Ortsbezug der Pressemitteilungen (council/presse_orte.py).

Was hier gehalten wird:

1. Eine Sperrung aus dem Geoportal wird zur Zeile mit Fließtext, Daten,
   Pin auf der Linie und den berührten Ortsbereichen.
2. Der Tageslauf schreibt fort statt zu ersetzen: Verschwundenes wird
   beendet, nicht gelöscht; die Tafel zeigt nur Laufendes im eigenen Bereich.
3. Eine Mitteilung findet ihren Ortsbereich über Katalog-Orte und bekannte
   Straßen; stadtweite und Rundumschläge bleiben ohne Ort — und werden nicht
   jede Nacht neu geprüft.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _ROOT / "web" / "backend"
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_BACKEND))

# Wegwerf-Datenbanken und die übrigen Testwerte kommen aus
# `tests/conftest.py` — dort EINMAL je Prozess gesetzt, damit sie nicht an
# der Import-Reihenfolge der Module hängen (siehe die Begründung dort).

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from council import geo, presse_orte, sperrungen  # noqa: E402
from council.store import CouncilStore  # noqa: E402

COUNCIL_DB = os.environ["COUNCIL_DB"]


@pytest.fixture(autouse=True)
def fresh_db():
    for suffix in ("", "-wal", "-shm"):
        Path(COUNCIL_DB + suffix).unlink(missing_ok=True)
    yield


def _linie_in(name: str, d: float = 0.003) -> dict:
    lat, lon = geo.ortsbereich_center(name)
    return {"type": "LineString", "coordinates": [[lon - d, lat], [lon + d, lat]]}


def _feature(objectid: int, street: str, name: str, **p) -> dict:
    props = {"OBJECTID": objectid, "Strasse": street, "Grund": "Bauarbeiten", "Art": 3,
             "von": 1725148800000, "bis": None, "Beschreibung": "Voll gesperrt.<br/>Umleitung &uuml;ber B", **p}
    return {"properties": props, "geometry": _linie_in(name)}


def test_normiere_sperrung():
    z = sperrungen.normiere(_feature(7, "Sandkruger Straße", "Kreyenbrück", bis=1735689600000))
    assert z["street"] == "Sandkruger Straße" and z["kind_label"] == "Vollsperrung"
    assert z["valid_from"] == "2024-09-01" and z["valid_until"] == "2025-01-01"
    assert z["description"] == "Voll gesperrt.\nUmleitung über B"
    assert geo.ortsbereich_for(z["lat"], z["lon"]) == "Kreyenbrück"
    assert z["places"][0]["place_id"] == "kreyenbrueck" and z["places"][0]["share"] == 1.0
    assert sperrungen.normiere({"properties": {"OBJECTID": 1, "Strasse": ""}}) is None


def test_sperrungen_werden_fortgeschrieben_und_je_viertel_gelesen():
    store = CouncilStore(COUNCIL_DB)
    zeilen = [sperrungen.normiere(_feature(1, "Sandkruger Straße", "Kreyenbrück")),
              sperrungen.normiere(_feature(2, "Hauptstraße", "Eversten"))]
    assert store.save_road_closures(zeilen) == {"laufend": 2, "neu": 2, "aktualisiert": 0, "beendet": 0}
    assert [c["street"] for c in store.district_road_closures("kreyenbrueck")] == ["Sandkruger Straße"]
    assert store.district_road_closures("kreyenbrueck")[0]["geometry"]["type"] == "LineString"
    assert store.district_road_closures("fliegerhorst") == []
    # Am nächsten Tag ist die Hauptstraße aus der Liste — beendet, nicht weg.
    stats = store.save_road_closures(zeilen[:1])
    assert stats["aktualisiert"] == 1 and stats["beendet"] == 1
    assert store.district_road_closures("eversten") == []
    assert store._conn.execute("SELECT status, ended_at FROM council_road_closures WHERE objectid = 2").fetchone()[0] == "beendet"
    # Taucht sie wieder auf, lebt sie wieder.
    store.save_road_closures(zeilen)
    assert [c["street"] for c in store.district_road_closures("eversten")] == ["Hauptstraße"]
    store.close()


def _konto(client: TestClient, email: str = "leserin@example.org") -> str:
    """Ein aktives Konto samt Bearer-Token — wie in test_district_projects.py."""
    r = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 201, r.text
    from kern.store import Store
    s = Store(os.environ["RATSLOTSE_DB"])
    with s._conn:
        s._conn.execute("UPDATE web_users SET status = 'active' WHERE email = ?", (email,))
    s.close()
    r = client.post("/api/auth/login", json={"email": email, "password": "password123"}, headers={"X-Client": "app"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _seed_presse(store: CouncilStore) -> None:
    c = store._conn
    with c:
        c.executemany(
            "INSERT INTO council_locations (slug, name, kind, district, local_area_id, updated_at) "
            "VALUES (?, ?, ?, ?, ?, '2026-01-01')",
            [("sandkruger-strasse", "Sandkruger Straße", "street", "Kreyenbrück", "kreyenbrueck")])
        c.executemany(
            "INSERT INTO council_location_districts (location_slug, district, place_id, share) VALUES (?, ?, ?, ?)",
            [("sandkruger-strasse", "Kreyenbrück", "kreyenbrueck", 0.6),
             ("sandkruger-strasse", "Bümmerstede", "buemmerstede", 0.4)])
        c.executemany(
            "INSERT INTO council_press (id, url, news_id, title, date, text, fetched_at) VALUES (?, ?, ?, ?, ?, ?, '2026-09-01')",
            [(1, "https://example.org/p/1", 1, "Sandkruger Straße: Zweiter Bauabschnitt beginnt", "2026-09-01",
              "Die Sanierung der Sandkruger Straße geht in den zweiten Abschnitt."),
             (2, "https://example.org/p/2", 2, "Folgenutzung der Halle 4 auf dem Fliegerhorst gesichert", "2026-09-02",
              "Die Stadt hat den Vertrag unterzeichnet."),
             (3, "https://example.org/p/3", 3, "Haushaltssatzung 2027: Rat berät den Entwurf", "2026-09-03",
              "Der Kämmerer stellt den Haushalt vor. Kreyenbrück und Eversten kommen auch vor."),
             (4, "https://example.org/p/4", 4, "Stadtfest: Gute Stimmung in der Innenstadt", "2020-01-01",
              "Alt.")])


def test_presse_findet_ortsbereich_ueber_strasse_und_katalog():
    store = CouncilStore(COUNCIL_DB)
    _seed_presse(store)
    offen = store.press_without_places()
    assert [r["id"] for r in offen] == [3, 2, 1, 4]
    stats = presse_orte.verorte(store, offen)
    assert stats == {"verortet": 3, "ohne Ort": 1}
    krey = store.district_press("kreyenbrueck", days=3650)
    assert [p["id"] for p in krey] == [1] and krey[0]["via"] == "street" and krey[0]["evidence"] == "Sandkruger Straße"
    fh = store.district_press("fliegerhorst", days=3650)
    assert [p["id"] for p in fh] == [2] and fh[0]["via"] == "catalog"
    # Die Haushaltssatzung ist stadtweit — auch wenn sie Ortsbereiche nennt.
    assert store.district_press("eversten", days=3650) == []
    # Alles ist geprüft, auch das ohne Ort: Der nächste Lauf findet nichts Offenes.
    assert store.press_without_places() == []
    # Das Zeitfenster gilt: 2020 ist zu alt für die Tafel.
    assert store.district_press("innenstadt", days=120) == []
    store.close()


def test_rundumschlag_bleibt_ohne_ort():
    store = CouncilStore(COUNCIL_DB)
    viele = ", ".join(n for n in geo.ortsbereiche()[:8])
    assert presse_orte.verorte_eine(store, f"Glasfaser: Ausbau in {viele}", "") == []
    assert presse_orte.verorte_eine(store, "", "") == []
    store.close()


def test_tafel_traegt_sperrungen_und_presse():
    store = CouncilStore(COUNCIL_DB)
    _seed_presse(store)
    presse_orte.verorte(store, store.press_without_places())
    store.save_road_closures([sperrungen.normiere(_feature(1, "Sandkruger Straße", "Kreyenbrück"))])
    store.close()
    client = TestClient(app)
    # Die Tafel verlangt seit dem Umzug auf die Stadtkarte ein Konto (Schritt 5).
    client.headers["Authorization"] = f"Bearer {_konto(client)}"
    tafel = client.get("/api/districts/kreyenbrueck/projects").json()
    assert [c["street"] for c in tafel["closures"]] == ["Sandkruger Straße"]
    assert tafel["closures"][0]["kind_label"] == "Vollsperrung"
    assert [p["title"][:9] for p in tafel["press"]] == ["Sandkruge"]
    assert tafel["press"][0]["url"].startswith("https://example.org/")
