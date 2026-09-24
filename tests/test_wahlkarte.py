"""Die Wahlkarte je Bezirk (``/api/wahlabend/karte``, docs/plan-viertel-wahlkarte.md).

Was hier festgehalten wird, sind die Zahlen, an denen man sieht, ob die Karte
stimmt — gemessen am 23.09.2026 an der eingefrorenen Ratswahl und am ersten
OB-Wahlgang: wer in wie vielen Urnenbezirken vorn lag, Krusenbusch als die
Ausnahme, die Briefwahl als Drittel ohne Fläche. Und die Zuordnung der
Bezirke zu den Ortsbereichen, die nicht ineinander liegen.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))
sys.path.insert(0, str(WURZEL / "scripts"))

from app.election import archive, district_map  # noqa: E402
from app.routers import wahlabend as router  # noqa: E402

VOR_DER_STICHWAHL = datetime(2026, 9, 23, 12, tzinfo=timezone.utc)
GEO = WURZEL / "web" / "frontend" / "public" / "geo"


@pytest.fixture(autouse=True)
def _frei(monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    monkeypatch.delenv("WAHLABEND_ELECTION", raising=False)
    archive.reset()
    yield
    archive.reset()


@pytest.fixture(scope="module")
def rat():
    return district_map.build("ratswahl-2026", now=VOR_DER_STICHWAHL)


def test_ratswahl_wer_vorn_lag(rat):
    assert rat["election"]["label"] == "Ratswahl"
    assert rat["total"] == rat["counted"] == 91 and rat["phase"] == "complete"
    siege = {w["slug"]: w["districts"] for w in rat["wins"]}
    # 47 + 39 + 2 + 1 = 89 — zwei Gleichstände: Bezirk 400 (Grüne : SPD,
    # 361 : 361) und, erst im amtlichen Endergebnis, Bezirk 208 (Linke : SPD,
    # 452 : 452). Vorläufig waren es 48 SPD-Bezirke und ein Gleichstand.
    assert siege == {"spd": 47, "gruene": 39, "afd": 2, "linke": 1}
    d = {x["number"]: x for x in rat["districts"]}
    assert d[400]["counted"] and d[400]["leader"] is None and d[400]["margin_pct"] == 0.0
    assert d[208]["leader"] is None and rat["ties"] == 2
    assert d[515]["leader"] == "afd" and d[515]["runner_up"] == "spd"
    assert d[515]["margin_pct"] == pytest.approx(8.8, abs=0.05)
    assert d[515]["name"] == "Grundschule Krusenbusch"
    assert d[205]["leader"] == "linke"


def test_ratswahl_briefwahl_ist_ein_drittel_ohne_flaeche(rat):
    assert rat["postal_share_pct"] == pytest.approx(32.3, abs=0.05)
    assert all(x["number"] < 900 for x in rat["districts"])
    # Die Wahlbereiche tragen die Briefwahl mit: je Bereich mehr Stimmen als
    # seine Urnenbezirke zusammen.
    for a in rat["areas"]:
        urne = sum(x["valid_votes"] or 0 for x in rat["districts"] if x["area"] == a["number"])
        assert a["valid_votes"] > urne, a["roman"]


def test_anteile_sortiert_und_farben_da(rat):
    for x in rat["districts"]:
        stimmen = [p["votes"] or 0 for p in x["parties"]]
        assert stimmen == sorted(stimmen, reverse=True)
    for c in rat["contestants"]:
        assert c["color"].startswith("#") and c["color_dark"].startswith("#")


def test_ortsbereich_innenstadt_hat_bezirke():
    k = district_map.build("ratswahl-2026", "Innenstadt", now=VOR_DER_STICHWAHL)
    assert k["place"] == "Innenstadt"
    assert {x["number"] for x in k["districts"]} >= {203, 204, 205}
    # Nur die Wahlbereiche, die die Bezirke berühren — und die Stadtzahlen
    # (Siege, Briefwahl) bleiben die der ganzen Stadt.
    assert {a["number"] for a in k["areas"]} == {x["area"] for x in k["districts"]}
    assert sum(w["districts"] for w in k["wins"]) == 89 and k["ties"] == 2


def test_ob_wahl_personen_statt_listen():
    k = district_map.build("ob-2026", now=VOR_DER_STICHWAHL)
    assert k["election"]["label"] == "OB-Wahl" and k["counted"] == 91
    siege = {w["slug"]: w["districts"] for w in k["wins"]}
    assert siege == {"prange": 60, "rohr": 31}
    kurz = {c["slug"]: c["short"] for c in k["contestants"]}
    assert kurz["prange"] == "Prange" and kurz["rohr"] == "Rohr"


def test_stichwahl_erst_nach_wahlschluss():
    slugs = [w.slug for w in district_map.choices(VOR_DER_STICHWAHL)]
    assert slugs == ["ratswahl-2026", "ob-2026"]
    danach = datetime(2026, 9, 27, 17, 0, tzinfo=timezone.utc)
    assert [w.slug for w in district_map.choices(danach)][-1] == "ob-stichwahl-2026"


def test_stichwahl_zweite_farbe_orange(monkeypatch):
    stich = district_map.elections.get("ob-stichwahl-2026")
    assert stich is not None
    monkeypatch.setattr(district_map.mayor, "fetch", lambda w=None, force=False: type("R", (), {"districts": ()})())
    wer, _ = district_map._mayor(stich)
    farben = {c["slug"]: c["color"] for c in wer}
    # Prange lag im ersten Wahlgang vorn und behält SPD-Rot, Rohr wird orange.
    assert farben["rohr"] == district_map.RUNOFF_SECOND[0]
    assert farben["prange"] != district_map.RUNOFF_SECOND[0]


def test_router_404_fuer_unbekanntes():
    with pytest.raises(HTTPException) as e:
        router.wahlabend_karte_je_bezirk(wahl="ratswahl-2021", place=None)
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        router.wahlabend_karte_je_bezirk(wahl=None, place="Atlantis")
    assert e.value.status_code == 404


def test_router_hinter_dem_schalter(monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "")
    with pytest.raises(HTTPException) as e:
        router.wahlabend_karte_je_bezirk(wahl=None, place=None)
    assert e.value.status_code == 404


# ------------------------------------------------------------------ Zuordnung

def test_ueberlappung_ist_aktuell():
    """Die eingecheckte Datei ist die, die das Skript heute rechnen würde —
    sonst hat jemand die Umrisse neu geholt und die Anteile vergessen."""
    import wahl_geodaten

    bezirke = json.loads((GEO / "wahlbezirke-oldenburg.json").read_text(encoding="utf-8"))["features"]
    orte = json.loads((GEO / "stadtteile-oldenburg.json").read_text(encoding="utf-8"))["features"]
    frisch = wahl_geodaten.anteile(bezirke, orte)
    liegt = json.loads(district_map.OVERLAP_PATH.read_text(encoding="utf-8"))["districts"]
    assert {str(k): v for k, v in frisch.items()} == liegt


def test_ueberlappung_deckt_alles():
    tabelle = district_map.overlap()
    orte = {f["properties"]["name"] for f in
            json.loads((GEO / "stadtteile-oldenburg.json").read_text(encoding="utf-8"))["features"]}
    assert len(tabelle) == 91
    for nr, eintraege in tabelle.items():
        assert eintraege, nr
        assert sum(e["share"] for e in eintraege) == pytest.approx(1.0, abs=0.01), nr
        assert all(e["name"] in orte for e in eintraege), nr
    # Innenstadt und Drielake haben keinen Bezirk, der überwiegend in ihnen
    # liegt — kommen aber vor (Messung 2 im Plan).
    assert district_map.places() == orte
    anteil_204 = {e["name"]: e["share"] for e in tabelle[204]}
    assert anteil_204["Innenstadt"] < 0.5


def test_app_buendelt_dieselben_bezirke_wie_das_web():
    """Die App bringt die Bezirks-Umrisse im Bundle mit. Holt jemand sie neu
    (`wahl_geodaten.py hol`), muss die Kopie mit — sonst färbt die App die
    Nummern von heute auf die Flächen von gestern."""
    web = (GEO / "wahlbezirke-oldenburg.json").read_bytes()
    app = (WURZEL / "ios" / "Resources" / "wahlbezirke-oldenburg.json").read_bytes()
    assert web == app, "ios/Resources/wahlbezirke-oldenburg.json neu kopieren"
