"""Die Karten zum Teilen — ``GET /api/wahlabend/karte.png``.

Drei Karten (Liste, Liste im Wahlbereich, Person) aus demselben Stand wie
die Seite. Geprüft wird, was sonst niemand merkt: dass jede Art ein PNG in
der versprochenen Größe liefert, dass eine Kombination, die es nicht gibt,
404 antwortet statt eine leere Karte zu malen, dass Lotti fehlen darf, ohne
die Karte zu kosten — und dass der Feature-Schalter auch hier gilt.
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import service, share  # noqa: E402


def _groesse(png: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(png)) as im:
        assert im.format == "PNG"
        return im.size


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    service.reset()
    yield TestClient(app)
    service.reset()


@pytest.fixture(scope="module")
def stand():
    return service.probe(60)


# ------------------------------------------------------------------ Auswahl

def test_auswahl_loest_liste_wahlbereich_und_platz_auf(stand):
    partei = share.select(stand, "gruene", None, None)
    assert partei and partei.kind == "party" and partei.party["slug"] == "gruene"
    bereich = share.select(stand, "gruene", 1, None)
    assert bereich and bereich.kind == "area" and bereich.area and bereich.area["number"] == 1
    person = share.select(stand, "gruene", 1, 2)
    assert person and person.kind == "candidate" and person.candidate and person.candidate["position"] == 2


def test_auswahl_kennt_kein_erfinden(stand):
    assert share.select(stand, "gibt-es-nicht", None, None) is None
    assert share.select(stand, "gruene", 99, None) is None
    assert share.select(stand, "gruene", 1, 99) is None
    # Ein Listenplatz ohne Wahlbereich ist keine Karte.
    assert share.select(stand, "gruene", None, 2) is None
    # Der Einzelwahlvorschlag tritt nur in einem Wahlbereich an.
    stille = next(p for p in stand["parties"] if p["kind"] == "einzelbewerber")
    bereiche = [a["number"] for a in stand["areas"] if any(p["slug"] == stille["slug"] for p in a["parties"])]
    assert len(bereiche) == 1
    fremd = next(n for n in range(1, 7) if n not in bereiche)
    assert share.select(stand, stille["slug"], fremd, None) is None


# ------------------------------------------------------------------ Bild

GROESSEN = {"beitrag": (1080, 1350), "story": (1080, 1920), "quer": (1200, 630)}


def test_jede_kartenart_liefert_jedes_format_in_seiner_groesse(stand):
    assert set(GROESSEN) == set(share.LAYOUTS) == set(share.FORMATS)
    for args in (("gruene", None, None), ("gruene", 1, None), ("gruene", 1, 2), ("spd", 3, 1)):
        auswahl = share.select(stand, *args)
        assert auswahl, args
        for fmt, groesse in GROESSEN.items():
            assert _groesse(share.render(stand, auswahl, fmt)) == groesse, (args, fmt)
    # Ohne Format: der Beitrag — das ist, was auf Instagram gepostet wird.
    assert _groesse(share.render(stand, share.select(stand, "gruene", None, None))) == (1080, 1350)  # type: ignore[arg-type]


def test_karten_vor_und_nach_der_auszaehlung(stand):
    """Vor der Auszählung gibt es keine Stimmen, aber eine Karte; danach
    trägt die Person einen Status."""
    vorher = service.probe(0)
    for args in (("gruene", None, None), ("gruene", 1, 2)):
        auswahl = share.select(vorher, *args)
        assert auswahl
        assert _groesse(share.render(vorher, auswahl, "story")) == (1080, 1920)
    fertig = service.probe(None)
    assert fertig["phase"] == "complete"
    person = share.select(fertig, "gruene", 1, 1)
    assert person and person.candidate
    text, _, _ = share._status(person.candidate, fertig["phase"], fertig["person_votes_available"])
    assert text.startswith("gewählt") or text == "nicht gewählt"


def test_karte_ohne_lotti_und_ohne_schriften_kommt_trotzdem(monkeypatch, tmp_path, stand):
    from app.election import image

    monkeypatch.setattr(share, "SPRITE_DIR", tmp_path / "keine-sprites")
    monkeypatch.setattr(share, "_sprite_cache", {})
    monkeypatch.setattr(image, "FONT_DIR", tmp_path / "keine-schriften")
    monkeypatch.setattr(image, "_font_cache", {})
    auswahl = share.select(stand, "gruene", 1, 2)
    assert auswahl
    assert _groesse(share.render(stand, auswahl, "quer")) == (1200, 630)


def test_lotti_kommt_aus_den_sprites_der_app():
    """Die Sprite-Sheets liegen im Repo; ein Bild daraus ist eine 384er-Kachel
    mit durchsichtigem Rand."""
    for pose, (sheet, index) in share.POSES.items():
        frame = share._frame(sheet, index)
        assert frame is not None, pose
        assert frame.size == (384, 384)
        assert frame.getpixel((0, 0))[3] == 0, f"{pose}: Kachel ohne durchsichtigen Rand"


def test_personenname_wird_umgedreht():
    assert share._person_name("Gerding, Anne Gesa") == "Anne Gesa Gerding"
    assert share._person_name("Hinrichs, Joachim Dr.") == "Joachim Dr. Hinrichs"
    assert share._person_name("Listenplatz 4 (nicht im Register)") == "Listenplatz 4 (nicht im Register)"


def test_abstaende_zur_vorwahl_in_worten():
    """Wie die Vorwahl heißt, kommt seit 09/2026 aus der Antwort — der Name
    steht nicht mehr in vier Zeichenketten im Bildcode."""
    partei = {"share_pct": 25.2, "share_previous_pct": 31.2, "seats_previous": 16}
    assert share._share_delta(partei, "2021") == "−6,0 Punkte zu 2021"  # type: ignore[arg-type]
    assert share._seat_delta(partei, 13, "2021") == "−3 Sitze zu 2021"  # type: ignore[arg-type]
    assert share._seat_delta(partei, 17, "2021") == "+1 Sitz zu 2021"  # type: ignore[arg-type]
    assert share._seat_delta(partei, 16, "2021") == "wie 2021"  # type: ignore[arg-type]
    # Dieselbe Partei, andere Vorwahl: Nur das Etikett wechselt.
    assert share._seat_delta(partei, 16, "2026") == "wie 2026"  # type: ignore[arg-type]
    neu = {"share_pct": 3.0, "share_previous_pct": None, "seats_previous": None}
    assert share._share_delta(neu, "2021") == "neu angetreten"  # type: ignore[arg-type]


# ------------------------------------------------------------------ Endpunkt

def test_karten_endpunkt_ist_hinter_dem_schalter(client, monkeypatch):
    monkeypatch.delenv("FEATURE_FLAGS", raising=False)
    assert client.get("/api/wahlabend/karte.png?list=gruene&probe=2021&counted=60").status_code == 404

    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    r = client.get("/api/wahlabend/karte.png?list=gruene&probe=2021&counted=60")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "image/png"
    assert "max-age=60" in r.headers["cache-control"]
    assert _groesse(r.content) == (1080, 1350)


def test_karten_endpunkt_kennt_die_drei_formate(client, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    q = "list=gruene&area=1&position=2&probe=2021&counted=60"
    for fmt, groesse in GROESSEN.items():
        r = client.get(f"/api/wahlabend/karte.png?{q}&format={fmt}")
        assert r.status_code == 200, fmt
        assert _groesse(r.content) == groesse, fmt
    assert client.get(f"/api/wahlabend/karte.png?{q}&format=quadrat").status_code == 422


def test_listenkarte_ohne_vergleich_zu_2021(client, monkeypatch):
    """Wer teilt, muss den Verlust nicht mitteilen: ``compare=false`` lässt
    den Abstand zu 2021 weg — und die Karte sieht dann anders aus."""
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    q = "list=gruene&probe=2021&counted=60&format=beitrag"
    mit = client.get(f"/api/wahlabend/karte.png?{q}")
    ohne = client.get(f"/api/wahlabend/karte.png?{q}&compare=false")
    assert mit.status_code == ohne.status_code == 200
    assert mit.content != ohne.content
    assert _groesse(ohne.content) == (1080, 1350)


def test_karten_endpunkt_unterscheidet_die_drei_arten_und_kennt_404(client, monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    q = "probe=2021&counted=60"
    liste = client.get(f"/api/wahlabend/karte.png?list=gruene&{q}")
    bereich = client.get(f"/api/wahlabend/karte.png?list=gruene&area=1&{q}")
    person = client.get(f"/api/wahlabend/karte.png?list=gruene&area=1&position=2&{q}")
    assert liste.status_code == bereich.status_code == person.status_code == 200
    assert len({liste.content, bereich.content, person.content}) == 3, "zwei Karten sehen gleich aus"
    # Zweimal dieselbe Karte kommt aus dem Zwischenspeicher.
    assert client.get(f"/api/wahlabend/karte.png?list=gruene&area=1&position=2&{q}").content == person.content

    assert client.get(f"/api/wahlabend/karte.png?list=gibt-es-nicht&{q}").status_code == 404
    assert client.get(f"/api/wahlabend/karte.png?list=gruene&area=9&{q}").status_code == 404
    assert client.get(f"/api/wahlabend/karte.png?list=gruene&area=1&position=99&{q}").status_code == 404
    assert client.get(f"/api/wahlabend/karte.png?list=gruene&position=2&{q}").status_code == 404
    assert client.get(f"/api/wahlabend/karte.png?{q}").status_code == 422
    assert client.get(f"/api/wahlabend/karte.png?list=Grüne&{q}").status_code == 422
