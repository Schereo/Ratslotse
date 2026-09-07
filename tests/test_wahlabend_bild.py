"""Das teilbare Bild des Wahlabends — ``GET /api/wahlabend/bild.png``.

Geprüft wird, was sonst niemand merkt: dass wirklich ein PNG in der
versprochenen Größe herauskommt (ein kaputter Byte-Strom sieht in der
Antwort aus wie ein Erfolg), dass der Feature-Schalter auch fürs Bild gilt,
dass es die Phase vor der Auszählung überlebt — und dass die Halbkreis-
Geometrie dieselbe ist wie im Web. Zwei Halbkreise, die sich um einen Platz
unterscheiden, sähen aus wie zwei verschiedene Ergebnisse.
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))
# Wegwerf-Datenbanken und die übrigen Testwerte kommen aus
# `tests/conftest.py` — dort EINMAL je Prozess gesetzt, damit sie nicht an
# der Import-Reihenfolge der Module hängen (siehe die Begründung dort).

from app.election import image, service  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    service.reset()
    yield TestClient(app)
    service.reset()


# ------------------------------------------------------------------ Geometrie

def test_halbkreis_hat_genau_n_plaetze_von_links_nach_rechts():
    """Wie ``halbkreis()`` in ``web/frontend/lib/wahlabend.ts``: n Plätze, nach
    Winkel sortiert, in einem Kasten von 2 × 1 mit Mittelpunkt 1|1."""
    import math

    assert image.semicircle(0) == [] and image.semicircle(-3) == []
    for n in (1, 5, 27, 52, 133):
        plaetze = image.semicircle(n)
        assert len(plaetze) == n, f"{n} Sitze, aber {len(plaetze)} Plätze"
        # „Links nach rechts" heißt: nach WINKEL, von π (links) nach 0 (rechts).
        # Nach der x-Achse wäre es falsch — bei gleichem Winkel steht die
        # äußere Reihe weiter links, und die Reihen greifen ineinander.
        winkel = [math.atan2(1 - p.y, p.x - 1) for p in plaetze]
        # Toleranz, weil zwei Reihen denselben Winkel treffen können und die
        # Gleitkommazahl dann um ein paar ULP auseinanderliegt — im Frontend
        # genauso, es rechnet dieselbe Formel.
        assert all(a >= b - 1e-9 for a, b in zip(winkel, winkel[1:])), \
            "die Plätze stehen nicht links nach rechts"
        for reihe in range(3):
            xs = [p.x for p in plaetze if p.row == reihe]
            assert xs == sorted(xs), f"Reihe {reihe} steht nicht links nach rechts"
        assert all(0 <= p.x <= 2 and 0 <= p.y <= 1 for p in plaetze)
        assert all(p.r > 0 for p in plaetze)

    # Die Aufteilung auf die Reihen ist die des Frontends (Umfangsverhältnis,
    # der Rest wandert von außen nach innen): 52 Sitze → 11 / 17 / 24.
    plaetze = image.semicircle(52)
    verteilung = [sum(1 for p in plaetze if p.row == i) for i in range(3)]
    assert verteilung == [11, 17, 24]
    assert plaetze[0].x < 0.6 and plaetze[-1].x > 1.4


# ------------------------------------------------------------------ Rendern

def _groesse(png: bytes) -> tuple[int, int]:
    from PIL import Image

    bild = Image.open(BytesIO(png))
    bild.load()
    assert bild.format == "PNG"
    return bild.size


def test_render_vor_der_auszaehlung_liefert_ein_gueltiges_png():
    """Phase „before": kein Halbkreis, aber ein Bild — sonst wäre die Seite
    ausgerechnet um 17:55 ohne Vorschau."""
    daten = service.probe(0)
    assert daten["phase"] == "before"
    for feld in ("seats", "projected_seats"):
        assert _groesse(image.render(daten, feld)) == (1200, 630)


def test_render_ohne_schriften_faellt_zurueck(monkeypatch, tmp_path):
    """Das Bild darf nie an einer Schrift scheitern."""
    monkeypatch.setattr(image, "FONT_DIR", tmp_path / "gibt-es-nicht")
    monkeypatch.setattr(image, "_font_cache", {})
    assert _groesse(image.render(service.probe(60), "seats")) == (1200, 630)


# ------------------------------------------------------------------ Endpunkt

def test_bild_endpunkt_ist_hinter_dem_schalter(client, monkeypatch):
    monkeypatch.delenv("FEATURE_FLAGS", raising=False)
    assert client.get("/api/wahlabend/bild.png?probe=2021&counted=60").status_code == 404

    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    r = client.get("/api/wahlabend/bild.png?probe=2021&counted=60")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/png"
    assert "max-age=60" in r.headers["cache-control"]
    assert _groesse(r.content) == (1200, 630)


def test_bild_endpunkt_kennt_beide_felder_und_haelt_das_ergebnis(client, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    stand = client.get("/api/wahlabend/bild.png?probe=2021&counted=60&feld=seats")
    hoch = client.get("/api/wahlabend/bild.png?probe=2021&counted=60&feld=projected_seats")
    assert stand.status_code == hoch.status_code == 200
    assert stand.content != hoch.content, "Stand und Hochrechnung sehen gleich aus"
    # Vorgabe während der Auszählung ist die Hochrechnung.
    assert client.get("/api/wahlabend/bild.png?probe=2021&counted=60").content == hoch.content
    # Und zweimal derselbe Stand kommt aus dem Zwischenspeicher.
    assert client.get("/api/wahlabend/bild.png?probe=2021&counted=60&feld=seats").content == stand.content

    assert client.get("/api/wahlabend/bild.png?probe=2021&counted=60&feld=quatsch").status_code == 422
