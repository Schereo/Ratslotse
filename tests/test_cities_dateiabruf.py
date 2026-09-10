"""Was ein Dokument-Abruf zurückgeben darf — und was nie.

Beide Regeln hier stammen aus derselben Wolfsburger Ernte (10.09.2026) und
haben dieselbe Form: Der Server antwortet mit HTTP 200, und trotzdem ist
nichts da. Ein Fehlercode wäre leicht zu behandeln; ein freundliches „hier,
bitte" mit dem falschen Inhalt ist es nicht.
"""
from __future__ import annotations

import requests

from council.cities.oparl import OParlClient
from council.cities.store import CitiesStore


class _Antwort:
    def __init__(self, inhalt: bytes, typ: str, status: int = 200):
        self.content = inhalt
        self.headers = {"content-type": typ}
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 500:
            raise requests.HTTPError(response=self)


class _Sitzung:
    def __init__(self, antwort):
        self.antwort = antwort
        self.headers: dict[str, str] = {}
        self.abrufe: list[str] = []

    def get(self, url, **_):
        self.abrufe.append(url)
        return self.antwort


def _client(tmp_path, antwort) -> OParlClient:
    store = CitiesStore(tmp_path / "raw.sqlite")
    return OParlClient(store, "teststadt", tmp_path / "files",
                       session=_Sitzung(antwort))


def test_eine_webseite_ist_nie_das_dokument(tmp_path):
    """ALLRIS liefert für die Anlage einer nichtöffentlichen Vorlage HTML.

    Kein Fehler, kein 403 — HTTP 200 und die Seite „Keine Information
    verfügbar". Gemessen an Wolfsburg: 444 von 1.798 Dateien. Ungeprüft
    landen sie als `.pdf` im Speicher, und die Textstufe meldet bei jedem Lauf
    „invalid pdf header" — Fehler, die wie ein Parserproblem aussehen und in
    Wahrheit eine Zugangsbeschränkung sind.
    """
    client = _client(tmp_path, _Antwort(
        b"\n<!DOCTYPE html>\n<html><body>Keine Information verf\xc3\xbcgbar</body></html>",
        "text/html; charset=utf-8"))
    assert client.get_file("https://x.example.org/anlage.pdf") is None
    client.raw.close()


def test_auch_ohne_ehrlichen_kopf_wird_html_erkannt(tmp_path):
    """Manche Server behaupten ``application/pdf`` und schicken eine Seite."""
    client = _client(tmp_path, _Antwort(
        b"<html><head><title>Fehler</title></head></html>", "application/pdf"))
    assert client.get_file("https://x.example.org/anlage.pdf") is None
    client.raw.close()


def test_ein_echtes_pdf_kommt_durch(tmp_path):
    client = _client(tmp_path, _Antwort(b"%PDF-1.7\n...", "application/pdf"))
    ergebnis = client.get_file("https://x.example.org/anlage.pdf")
    assert ergebnis is not None
    daten, mime = ergebnis
    assert daten.startswith(b"%PDF") and mime == "application/pdf"
    client.raw.close()


def test_eine_kaputte_adresse_kostet_keinen_abruf(tmp_path):
    """Ein lokaler Windows-Pfad statt eines Links — einmal in Wolfsburg.

    ``requests`` wirft dafür ``InvalidSchema``; ungefangen nahm das den
    ganzen Dateiabruf der Stadt mit. Ein anderes Schema wird nie gut, ein
    zweiter Versuch also sinnlos: gar nicht erst anfragen.
    """
    client = _client(tmp_path, _Antwort(b"%PDF-1.7", "application/pdf"))
    assert client.get_file("file:///C:/Users/vorname-n/Downloads/x.pdf") is None
    assert client.session.abrufe == [], "es darf kein Abruf stattgefunden haben"
    client.raw.close()
