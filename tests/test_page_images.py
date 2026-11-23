"""Seitenbilder für die Vorschau an Notiz-Verweisen (council/page_images.py).

Das Rendern braucht PyMuPDF — auf dev und Prod da, in der CI nicht; diese
Tests überspringen sich dort. Die Verdrahtung der Endpunkte (Konto, Kennung,
Fehlercodes) prüfen die Tests unten ohne PyMuPDF."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from council import page_images
from council.store import CouncilStore

RIS = "https://ratsinfo.oldenburg.de/bi/getfile.asp?id={}&type=do"


def _pdf(seiten: int) -> bytes:
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    for i in range(seiten):
        doc.new_page(width=595, height=842).insert_text((72, 100), f"Seite {i + 1}", fontsize=24)
    return doc.tobytes()


class _Antwort:
    def __init__(self, content: bytes):
        self.content = content


def _ratsinfo(monkeypatch, daten: bytes) -> list[str]:
    abgerufen: list[str] = []

    def fetch(_session, url, timeout=45):
        abgerufen.append(url)
        return _Antwort(daten)

    monkeypatch.setattr(page_images.ris, "fetch", fetch)
    return abgerufen


def test_eine_seite_wird_ein_jpeg_und_danach_nicht_neu_geholt(tmp_path, monkeypatch):
    abgerufen = _ratsinfo(monkeypatch, _pdf(3))
    bild = page_images.page_image(tmp_path, 312295, RIS.format(312295), 2, 640)
    assert bild.read_bytes()[:2] == b"\xff\xd8", "ein JPEG"
    assert page_images.page_count(tmp_path, 312295, RIS.format(312295)) == 3
    page_images.page_image(tmp_path, 312295, RIS.format(312295), 3, 320)
    assert abgerufen == [RIS.format(312295)], "das PDF kommt einmal vom Ratsinfo, dann aus der Ablage"


def test_eine_seite_die_es_nicht_gibt(tmp_path, monkeypatch):
    _ratsinfo(monkeypatch, _pdf(2))
    with pytest.raises(page_images.NoPreview) as e:
        page_images.page_image(tmp_path, 1, RIS.format(1), 9, 640)
    assert e.value.reason == "no_page"


def test_nur_das_ratsinfo_und_nur_pdfs(tmp_path, monkeypatch):
    abgerufen = _ratsinfo(monkeypatch, b"<html>Startseite</html>")
    with pytest.raises(page_images.NoPreview) as e:
        page_images.pdf_bytes(tmp_path, 1, "https://example.org/datei.pdf")
    assert e.value.reason == "not_ris" and abgerufen == []
    with pytest.raises(page_images.NoPreview) as e:
        page_images.pdf_bytes(tmp_path, 1, RIS.format(1))
    assert e.value.reason == "not_pdf"
    assert not (tmp_path / "pdf" / "1.pdf").exists(), "eine falsche Antwort landet nicht in der Ablage"


def test_zu_grosse_unterlagen_bekommen_keine_vorschau(tmp_path, monkeypatch):
    monkeypatch.setattr(page_images, "PDF_MAX_BYTES", 10)
    _ratsinfo(monkeypatch, b"%PDF-1.7" + b"x" * 100)
    with pytest.raises(page_images.NoPreview) as e:
        page_images.pdf_bytes(tmp_path, 1, RIS.format(1))
    assert e.value.reason == "too_large"


def test_die_ablage_hat_eine_obergrenze(tmp_path):
    ordner = tmp_path / "img"
    ordner.mkdir()
    for i in range(5):
        p = ordner / f"{i}.jpg"
        p.write_bytes(b"x" * 100)
        os.utime(p, (1000 + i, 1000 + i))
    page_images._trim(ordner, 250)
    assert sorted(p.name for p in ordner.iterdir()) == ["3.jpg", "4.jpg"], "die zuletzt benutzten bleiben"


def test_nur_vereinbarte_breiten(tmp_path):
    with pytest.raises(ValueError):
        page_images.page_image(tmp_path, 1, RIS.format(1), 1, 1000)


# --- Endpunkte: Konto, Kennung, Fehlercodes (ohne PyMuPDF) ------------------

@pytest.fixture
def client():
    from app.main import app
    from scripts.grant_admin import grant_admin

    for base in (os.environ["RATSLOTSE_DB"], os.environ["COUNCIL_DB"]):
        for suffix in ("", "-wal", "-shm"):
            Path(base + suffix).unlink(missing_ok=True)
    c = TestClient(app)
    c.post("/api/auth/register", json={"display_name": "Testkonto", "email": "admin@test.de", "password": "password123"})
    grant_admin("admin@test.de", os.environ["RATSLOTSE_DB"])
    return c


@pytest.fixture
def unterlage(monkeypatch, tmp_path):
    quelle = {"document_id": 312295, "url": RIS.format(312295), "n_pages": None}
    monkeypatch.setattr(CouncilStore, "document_source", lambda self, did: dict(quelle) if did == 312295 else None)
    bild = tmp_path / "seite.jpg"
    bild.write_bytes(b"\xff\xd8\xff\xe0JPEG")
    gerendert: list[tuple] = []

    def page_image(cache, did, url, page, w):
        gerendert.append((did, url, page, w))
        if page > 3:
            raise page_images.NoPreview("no_page")
        return bild

    monkeypatch.setattr(page_images, "page_image", page_image)
    monkeypatch.setattr(page_images, "page_count", lambda cache, did, url: 3)
    return gerendert


def test_die_seite_kommt_als_bild_mit_der_adresse_aus_der_datenbank(client, unterlage):
    r = client.get("/api/council/documents/312295/page/2?w=320")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert "immutable" in r.headers["cache-control"] and "private" in r.headers["cache-control"]
    assert unterlage == [(312295, RIS.format(312295), 2, 320)]
    assert client.get("/api/council/documents/312295/pages").json() == {"document_id": 312295, "n_pages": 3}


def test_fehler_haben_eigene_codes(client, unterlage, monkeypatch):
    assert client.get("/api/council/documents/999/page/1").status_code == 404
    assert client.get("/api/council/documents/312295/page/9").status_code == 404
    assert client.get("/api/council/documents/312295/page/0").status_code == 404
    assert client.get("/api/council/documents/312295/page/1?w=1000").status_code == 422

    def ohne(*a):
        raise page_images.NoPreview("unavailable")

    monkeypatch.setattr(page_images, "page_image", ohne)
    assert client.get("/api/council/documents/312295/page/1").status_code == 503


def test_ohne_konto_keine_vorschau(unterlage):
    from app.main import app

    anonym = TestClient(app)
    assert anonym.get("/api/council/documents/312295/page/1").status_code == 401
    assert anonym.get("/api/council/documents/312295/pages").status_code == 401
    assert unterlage == []
