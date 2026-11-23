"""Der Beteiligungsbericht-Cron verliert keinen Jahrgang mehr still.

Bis 11/2026 las ein Lauf, dessen Download für EINEN Bericht scheiterte, nur die
übrigen und ersetzte damit den Bestand — solange 80 % der Zeilen blieben.
Gemessen: Ohne den Bericht 2024 fielen alle 26 Werte für 2024 weg. Jetzt:

1. Jede geholte Fassung landet im Archiv (``council/archiv.py``).
2. Scheitert ein Download, wird die gesicherte Fassung gelesen.
3. Gibt es keine, hält ``beteiligungsbericht.einlesen`` den ganzen Bestand.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_beteiligungsbericht as cron  # noqa: E402
from council import beteiligungsbericht, finanzquellen, stadtdownload  # noqa: E402
from council.store import CouncilStore  # noqa: E402

BASE = "https://www.oldenburg.de/fileadmin/oldenburg/Benutzer/Dateien/20_Controlling_und_Finanzen/Beteiligungsbericht"
URL_2023 = f"{BASE}/Beteiligungsbericht_2023.pdf"
URL_2024 = f"{BASE}/Beteiligungsbericht_2024_kombiniert_final.pdf"
SEITE = (f'<a href="{URL_2023.removeprefix(stadtdownload.BASE)}">2023</a>'
         f'<a href="{URL_2024.removeprefix(stadtdownload.BASE)}">2024</a>')


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    """Ein leerer Store, ein leeres Archiv, keine Mail, kein Netz.

    ``einlesen`` wird mitgeschnitten statt ausgeführt: Hier geht es darum,
    WELCHE Dokumente der Cron ihm reicht, nicht um den Parser."""
    gereicht: list[dict] = []

    def einlesen(store, dokumente, p, schuetzen=True):
        gereicht.append({j: d["url"] for j, d in dokumente.items()})
        return {"gesellschaften": 1, "texte": 0, "indicators": 0, "verworfen": 0,
                "widersprueche": 0, "bestand_geschuetzt": 0,
                "jahrgaenge": sorted(dokumente)}

    monkeypatch.setattr(beteiligungsbericht, "einlesen", einlesen)
    monkeypatch.setattr(cron, "_seiten", lambda inhalt: [inhalt.decode("latin-1")])
    monkeypatch.setattr(cron, "_schon_gemeldet", lambda befund: True)
    monkeypatch.setattr(stadtdownload, "warte", lambda: None)
    db = tmp_path / "council.sqlite"
    CouncilStore(db).close()
    return {"db": str(db), "archiv": tmp_path / "archiv", "gereicht": gereicht}


def _lauf(u, monkeypatch, hole):
    monkeypatch.setattr(stadtdownload, "hole", hole)
    return cron.main(db=u["db"], heute=date(2026, 11, 23), still=True,
                     uebersicht_html=SEITE, archiv_pfad=u["archiv"],
                     protokoll=finanzquellen.Protokoll(still=True))


def _ok(url, last_modified=None, etag=None, session=None):
    return stadtdownload.Dokument(url=url, inhalt=b"%PDF " + url.encode(),
                                  last_modified="Mon, 02 Mar 2026 10:00:00 GMT",
                                  etag='"abc"')


def test_geholte_fassung_wird_gesichert(umgebung, monkeypatch):
    aus = _lauf(umgebung, monkeypatch, _ok)
    assert aus["Download-Fehler"] == 0
    ordner = umgebung["archiv"] / "beteiligungsbericht" / "Beteiligungsbericht_2024_kombiniert_final.pdf"
    assert [p.suffix for p in ordner.iterdir() if not p.name.startswith(".")] == [".pdf"]
    assert (ordner / cron.QUELLE).is_file()


def test_gescheiterter_download_liest_die_gesicherte_fassung(umgebung, monkeypatch):
    _lauf(umgebung, monkeypatch, _ok)

    def kaputt(url, last_modified=None, etag=None, session=None):
        if url == URL_2024:
            raise stadtdownload.DownloadFehler(f"{url}: HTTP 503")
        return _ok(url)

    aus = _lauf(umgebung, monkeypatch, kaputt)
    assert aus["Download-Fehler"] == 1
    assert aus["Aus dem Archiv gelesen"] == 1
    # Beide Jahrgänge kommen bei einlesen() an — der kaputte aus dem Archiv.
    assert umgebung["gereicht"][-1] == {2023: URL_2023, 2024: URL_2024}


def test_304_liest_die_gesicherte_fassung_und_schickt_die_kopfzeilen(umgebung, monkeypatch):
    _lauf(umgebung, monkeypatch, _ok)
    gesehen = []

    def unveraendert(url, last_modified=None, etag=None, session=None):
        gesehen.append((last_modified, etag))
        return stadtdownload.Dokument(url=url, inhalt=None,
                                      last_modified=last_modified, etag=etag)

    _lauf(umgebung, monkeypatch, unveraendert)
    assert gesehen == [("Mon, 02 Mar 2026 10:00:00 GMT", '"abc"')] * 2
    assert umgebung["gereicht"][-1] == {2023: URL_2023, 2024: URL_2024}


def test_ohne_gesicherte_fassung_fehlt_der_jahrgang(umgebung, monkeypatch):
    """Dann reicht der Cron nur die übrigen — und einlesen() muss den
    Bestand halten (nächster Test)."""
    def kaputt(url, last_modified=None, etag=None, session=None):
        if url == URL_2024:
            raise stadtdownload.DownloadFehler(f"{url}: HTTP 503")
        return _ok(url)

    aus = _lauf(umgebung, monkeypatch, kaputt)
    assert aus["Aus dem Archiv gelesen"] == 0
    assert umgebung["gereicht"][-1] == {2023: URL_2023}


def test_einlesen_haelt_den_bestand_wenn_ein_jahrgang_fehlt(tmp_path, monkeypatch):
    store = CouncilStore(tmp_path / "council.sqlite")
    monkeypatch.setattr(store, "beteiligungsbericht_jahre", lambda: [2022, 2023, 2024])
    monkeypatch.setattr(beteiligungsbericht, "lies", lambda seiten: {
        "gesellschaften": [object()], "budget_year": int(seiten[0]),
        "warnungen": [], "dokumentproben": []})
    gespeichert = []
    monkeypatch.setattr(store, "save_beteiligungsbericht",
                        lambda *a, **k: gespeichert.append(a))
    p = finanzquellen.Protokoll(still=True)
    dokumente = {j: {"seiten": [str(j)], "url": f"u{j}", "label": f"B {j}"}
                 for j in (2022, 2023)}
    try:
        aus = beteiligungsbericht.einlesen(store, dokumente, p)
    finally:
        store.close()
    assert aus["bestand_geschuetzt"] == 1
    assert aus["fehlende_jahrgaenge"] == [2024]
    assert not gespeichert
    assert any("2024" in w and "unangetastet" in w for w in p.warnungen)


def test_fehlende_jahrgaenge_nur_ab_dem_formatbruch():
    assert beteiligungsbericht.fehlende_jahrgaenge([2019, 2022, 2024], {2022: 1}) == [2024]
