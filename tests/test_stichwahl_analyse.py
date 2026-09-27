"""Die Stichwahl im Rückblick (``election.runoff_analysis``,
``/api/wahlabend/stichwahl/analyse``).

Gehalten gegen die beiden eingefrorenen Wahlgänge 2026 — ohne Netz. Die
Sollwerte sind am 27.09.2026 unabhängig davon aus den Rohdateien gerechnet
worden (Skript neben dem Modul, nicht im Repo), nicht aus dem Modul
abgeschrieben: Ein Test, der die eigene Ausgabe zurückliest, hält nichts.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import elections, runoff_analysis  # noqa: E402
from app.routers import wahlabend as router  # noqa: E402


@pytest.fixture(autouse=True)
def _frei(monkeypatch):
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    runoff_analysis.reset()
    yield
    runoff_analysis.reset()


@pytest.fixture
def analysis() -> dict:
    data = router.stichwahl_analyse()
    assert data is not None
    return dict(data)


def test_der_gewinner_steht_vorn_und_alle_anteile_sind_aus_seiner_sicht(analysis):
    assert analysis["winner"] == "rohr"
    assert [c["slug"] for c in analysis["candidates"]] == ["rohr", "prange"]
    rohr = analysis["candidates"][0]
    assert (rohr["votes_first"], rohr["votes_runoff"]) == (25850, 30792)
    assert (rohr["share_first_pct"], rohr["share_runoff_pct"]) == (30.54, 51.55)
    assert analysis["result_status"] == "vorlaeufig"


def test_stadt_stimmt_mit_den_zahlen_der_stadt(analysis):
    city = analysis["city"]
    assert city["districts"] == 133
    assert city["votes_first"] == {"rohr": 25850, "prange": 28075}
    assert city["votes_runoff"] == {"rohr": 30792, "prange": 28942}
    assert (city["voters_first"], city["voters_runoff"]) == (85991, 60096)
    # Wählende aller Bezirke durch Wahlberechtigte der Urnenbezirke — und das
    # ist genau die Beteiligung, die die Stadt meldet.
    assert city["turnout_first_pct"] == 63.46
    assert city["turnout_runoff_pct"] == 44.42
    assert city["share_first_pct"]["rohr"] == 47.94  # Anteil an den BEIDEN
    assert city["swing_pts"] == pytest.approx(51.55 - 47.94, abs=0.01)


def test_die_ausgeschiedenen_summieren_sich_zum_rest_des_ersten_wahlgangs(analysis):
    eliminated = analysis["eliminated"]
    assert [e["slug"] for e in eliminated][:2] == ["boldt", "butzin"]
    assert sum(e["votes"] for e in eliminated) + 25850 + 28075 == analysis["city"]["valid_first"] == 84656


def test_urne_hat_gedreht_brief_kaum(analysis):
    pots = {p["key"]: p for p in analysis["pots"]}
    assert (pots["urn"]["districts"], pots["postal"]["districts"]) == (91, 42)
    assert pots["urn"]["share_first_pct"]["rohr"] == 46.3
    assert pots["urn"]["share_runoff_pct"]["rohr"] == 51.08
    assert pots["postal"]["share_first_pct"]["rohr"] == 51.07
    assert pots["postal"]["share_runoff_pct"]["rohr"] == 52.27
    # An der Urne verlor Prange Stimmen, trotz des Wegfalls von sieben Namen.
    assert pots["urn"]["growth"]["prange"] < 1 < pots["urn"]["growth"]["rohr"]
    for key in ("votes_first", "votes_runoff"):
        assert pots["urn"][key]["rohr"] + pots["postal"][key]["rohr"] == analysis["city"][key]["rohr"]


def test_wahlbereiche_decken_die_stadt_ab_und_rohr_legt_ueberall_zu(analysis):
    areas = analysis["areas"]
    assert [a["label"] for a in areas] == [f"Wahlbereich {r}" for r in ("I", "II", "III", "IV", "V", "VI")]
    assert sum(a["districts"] for a in areas) == 133
    assert sum(a["votes_runoff"]["prange"] for a in areas) == 28942
    assert all(a["swing_pts"] > 0 for a in areas)
    assert {a["number"]: a["swing_pts"] for a in areas}[6] == max(a["swing_pts"] for a in areas)
    assert all(a["turnout_runoff_pct"] < a["turnout_first_pct"] for a in areas)


def test_fuenftel_aufholen_wo_er_schwach_war(analysis):
    quintiles = analysis["quintiles"]
    assert [q["rank"] for q in quintiles] == [1, 2, 3, 4, 5]
    assert sum(q["districts"] for q in quintiles) == 91  # nur Urne
    firsts = [q["share_first_pct"] for q in quintiles]
    assert firsts == sorted(firsts)
    assert quintiles[0]["swing_pts"] > quintiles[-1]["swing_pts"]
    # −0,345 ungerundet: je nach Rundung der Anteile −0,34 oder −0,35.
    assert analysis["catch_up_r"] == pytest.approx(-0.345, abs=0.006)


def test_gedrehte_bezirke_und_bezirke_vorn(analysis):
    assert analysis["lead_districts"]["first"]["rohr"] == 55
    assert analysis["lead_districts"]["runoff"]["rohr"] == 74
    assert analysis["flipped"] == {"rohr": 20, "prange": 1}


def test_die_rangliste_sortiert_und_filtert_auf_dem_server():
    swing = router.stichwahl_analyse_bezirke(sort="swing", area=None, pot=None)
    assert swing["total"] == 133 and len(swing["rows"]) == 133
    assert [r["rank"] for r in swing["rows"][:3]] == [1, 2, 3]
    assert swing["rows"][0]["number"] == 209  # Oberschule Osternburg, +13,2
    assert swing["rows"][0]["swing_pts"] == pytest.approx(13.19, abs=0.01)

    share = router.stichwahl_analyse_bezirke(sort="share", area=2, pot="urn")
    assert share["rows"] and all(r["area"] == 2 and not r["postal"] for r in share["rows"])
    shares = [r["share_runoff_pct"] for r in share["rows"]]
    assert shares == sorted(shares, reverse=True)

    postal = router.stichwahl_analyse_bezirke(sort="turnout", area=None, pot="postal")
    assert len(postal["rows"]) == 42
    assert all(r["turnout_first_pct"] is None for r in postal["rows"])

    turnout = router.stichwahl_analyse_bezirke(sort="turnout", area=None, pot=None)
    changes = [r["turnout_change_pts"] for r in turnout["rows"] if r["turnout_change_pts"] is not None]
    assert changes == sorted(changes)  # stärkster Rückgang zuerst
    assert turnout["rows"][-1]["postal"]  # ohne Beteiligung ans Ende

    number = router.stichwahl_analyse_bezirke(sort="number", area=None, pot=None)
    assert [r["number"] for r in number["rows"]][:2] == [101, 102]


def test_ohne_eingefrorene_stichwahl_gibt_es_keine_auswertung(monkeypatch):
    """Nie auf einem halben Abend rechnen: ohne Archiv 404."""
    w = elections.get("ob-stichwahl-2026")
    assert w is not None
    from dataclasses import replace
    frozen_get = elections.get
    monkeypatch.setattr(elections, "get", lambda slug: replace(w, archive_folder=None)
                        if slug == w.slug else frozen_get(slug))
    with pytest.raises(HTTPException) as info:
        router.stichwahl_analyse()
    assert info.value.status_code == 404


def test_der_erste_wahlgang_ist_keine_stichwahl():
    assert runoff_analysis.analyse("ob-2026") is None
