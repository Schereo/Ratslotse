"""Die Kartenflächen der Wahlbereiche und Wahlbezirke (``scripts/wahl_geodaten.py``).

Die Dateien liegen als statische Assets im Repo, geholt vom openGEOdata-Portal
der Stadt. Dieser Test fasst **kein Netz** an — er hält, was im Repo liegt,
gegen die Ergebnisdatei derselben Wahl. Genau dort läge der Fehler, den
niemand sähe: Eine Fläche, die es nicht mehr gibt, oder ein Wahlbezirk, der
nach der Neuaufteilung eine andere Nummer trägt, macht die Karte still falsch.

Die Vereinfachung (Douglas-Peucker) wird gegen ihre eigene Zusage geprüft:
Ringe bleiben geschlossen, und kein Punkt der Originalfläche wandert weiter
als die Toleranz.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL))

from scripts.wahl_geodaten import _abstand, _meter_je_grad, vereinfache  # noqa: E402

GEO = WURZEL / "web" / "frontend" / "public" / "geo"
REFERENZ = WURZEL / "kommunalwahl" / "referenz-2026" / "ratswahl-2026-wahlbezirke.csv"


def _lade(name: str) -> dict:
    return json.loads((GEO / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bereiche() -> dict:
    return _lade("wahlbereiche-oldenburg.json")


@pytest.fixture(scope="module")
def bezirke() -> dict:
    return _lade("wahlbezirke-oldenburg.json")


def test_sechs_wahlbereiche_und_einundneunzig_wahlbezirke(bereiche, bezirke):
    assert [f["properties"]["nr"] for f in bereiche["features"]] == [1, 2, 3, 4, 5, 6]
    nummern = [f["properties"]["nr"] for f in bezirke["features"]]
    assert len(nummern) == 91 and nummern == sorted(nummern)
    assert len(set(nummern)) == 91


def test_jeder_wahlbezirk_gehoert_zu_genau_einem_wahlbereich(bereiche, bezirke):
    zu = {f["properties"]["wb"] for f in bezirke["features"]}
    assert zu == {f["properties"]["nr"] for f in bereiche["features"]}
    # Die Hunderterstelle der Bezirksnummer IST der Wahlbereich (101…115 = I).
    for f in bezirke["features"]:
        assert f["properties"]["nr"] // 100 == f["properties"]["wb"]


def test_die_flaechen_passen_zur_ergebnisdatei_2026(bezirke):
    """Die Zusage, an der alles hängt: Ergebnis und Fläche treffen sich über
    die Bezirksnummer, ohne Zuordnungstabelle."""
    with REFERENZ.open(encoding="utf-8-sig") as fh:
        gemeldet = {int(r["gebiet-nr"]) for r in csv.DictReader(fh, delimiter=";")
                    if r["gebiet-nr"].isdigit()}
    urne = {n for n in gemeldet if n < 900}          # ab 900: Briefwahl, ohne Fläche
    flaechen = {f["properties"]["nr"] for f in bezirke["features"]}
    assert flaechen == urne
    assert len(gemeldet) - len(urne) == 42, "Briefwahlbezirke der Ratswahl 2026"


def test_jede_flaeche_traegt_ihren_namen(bezirke):
    for f in bezirke["features"]:
        assert f["properties"]["name"], f["properties"]["nr"]
    # Der Stadtbezirks-Name ist nicht eindeutig — mehrere Wahlbezirke teilen
    # sich einen (Bürgerfelde Süd hat vier). Die Nummer ist der Schlüssel.
    namen = [f["properties"]["name"] for f in bezirke["features"]]
    assert len(set(namen)) < len(namen)


def test_die_ringe_sind_geschlossen_und_gueltig(bereiche, bezirke):
    for sammlung in (bereiche, bezirke):
        for f in sammlung["features"]:
            geo = f["geometry"]
            assert geo["type"] in ("Polygon", "MultiPolygon")
            ringe = (geo["coordinates"] if geo["type"] == "Polygon"
                     else [r for teil in geo["coordinates"] for r in teil])
            for ring in ringe:
                assert len(ring) >= 4, f["properties"]
                assert ring[0] == ring[-1], f["properties"]
                for x, y in ring:
                    assert 7.9 < x < 8.4 and 53.0 < y < 53.3, "außerhalb Oldenburgs"


def test_die_dateien_bleiben_klein(bereiche, bezirke):
    """Die Karte lädt auf dem Handy. Roh sind die Wahlbezirke 439 KB; die
    Grenze hier ist großzügig gesetzt und fällt trotzdem auf, wenn jemand die
    Vereinfachung abschaltet (``hol --roh``)."""
    assert (GEO / "wahlbereiche-oldenburg.json").stat().st_size < 30 * 1024
    assert (GEO / "wahlbezirke-oldenburg.json").stat().st_size < 120 * 1024


def test_die_herkunft_steht_in_der_datei(bereiche, bezirke):
    for sammlung in (bereiche, bezirke):
        assert sammlung["license"] == "dl-zero-de/2.0"
        assert "Stadt Oldenburg" in sammlung["attribution"]
        assert sammlung["source"].startswith("https://services5.arcgis.com/")


def test_vereinfachen_verschiebt_keinen_punkt_weiter_als_die_toleranz():
    """Douglas-Peucker wirft Punkte weg, aber keiner der weggeworfenen liegt
    weiter als die Toleranz von der übrig gebliebenen Linie entfernt."""
    # Ein Quadrat von rund 1 km Kantenlänge, dessen Kanten in ~3-m-Zacken
    # verlaufen. Eine ZACKENFREIE Linie wäre kein Prüffall: Douglas-Peucker
    # behält bei einer entarteten Fläche (Ergebnis unter drei Punkten) den
    # Bestand, damit keine Fläche verschwindet.
    ring = []
    ecken = [(8.20, 53.150), (8.215, 53.150), (8.215, 53.159), (8.20, 53.159)]
    for i, (x0, y0) in enumerate(ecken):
        x1, y1 = ecken[(i + 1) % 4]
        for k in range(12):
            t = k / 12
            zacke = 0.00003 * (1 if k % 2 else -1)
            ring.append([x0 + (x1 - x0) * t + zacke, y0 + (y1 - y0) * t + zacke])
    ring.append(ring[0])
    fein = vereinfache({"type": "Polygon", "coordinates": [ring]}, 25.0)["coordinates"][0]
    assert len(fein) < len(ring) and fein[0] == fein[-1]
    # Gemessen wird gegen die LINIE, nicht gegen die übrig gebliebenen Punkte:
    # Eine gerade Kante von 1 km schrumpft auf ihre zwei Enden, und ihr
    # Mittelpunkt ist dann 500 m vom nächsten Punkt entfernt — aber 3 m von
    # der Kante. Das ist die Zusage des Verfahrens.
    mx, my = _meter_je_grad(53.15)
    for p in ring:
        nah = min(_abstand(p, fein[i], fein[i + 1], mx, my) for i in range(len(fein) - 1))
        assert nah <= 30.0   # 25 m Toleranz + Rundung auf fünf Stellen


def test_eine_winzige_flaeche_ueberlebt_die_vereinfachung():
    """Ein Ring, der schon minimal ist, darf nicht verschwinden — sonst fehlt
    eine Fläche, ohne dass jemand einen Fehler sieht."""
    winzig = [[8.2, 53.15], [8.2001, 53.15], [8.2001, 53.1501], [8.2, 53.15]]
    raus = vereinfache({"type": "Polygon", "coordinates": [winzig]}, 25.0)["coordinates"][0]
    assert len(raus) >= 4 and raus[0] == raus[-1]
