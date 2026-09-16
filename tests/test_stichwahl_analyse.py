"""Hält Bezugsgrößen, Wahljahr und Vollständigkeit an den Quelldaten.

Die historischen Stadtwerte sind unabhängig in den amtlichen
Bekanntmachungen belegt (Quellen in docs/stichwahl-analyse.md).
"""
from __future__ import annotations

import csv
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web" / "backend"))

from app.election import runoff_analysis as analysis  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import wahlabend  # noqa: E402


@pytest.fixture(scope="module")
def result():
    return analysis.compute()


def test_nichtteilnahme_bezieht_briefwahl_ein(result):
    t = result["totals"]
    assert t["eligible"] == 135513
    assert t["voters"] == t["urn_voters"] + t["postal_voters"] == 85991
    assert t["postal_voters"] == 27351
    assert t["non_voters"] == 49522 == t["eligible"] - t["voters"]
    assert t["valid_votes"] + t["invalid_ballots"] == t["voters"]
    assert t["turnout_pct"] == pytest.approx(63.4559046)
    assert result["district_count"] == result["urn_district_count"] + result["postal_district_count"] == 133


def test_alle_kandidaturen_einschliesslich_sonstige(result):
    assert sum(c["votes"] for c in result["candidates"]) == result["totals"]["valid_votes"]
    assert sum(c["share_all_pct"] for c in result["candidates"]) == pytest.approx(100)
    assert result["eliminated_votes"] == 30731
    assert result["grouped_other_votes"] == 1509
    assert result["eliminated_votes"] - result["grouped_other_votes"] == 29222
    assert result["lead_votes"] == 2225


def test_ratswahl_aus_2026_unabhaengig_von_aktiver_wahl(monkeypatch):
    # Eine andere aktive Wahl/Generalprobe darf die Analyse nicht verändern.
    monkeypatch.setenv("WAHLABEND_ELECTION", "existiert-nicht")
    actual = analysis.council()
    with (analysis.REFERENCE / "ratswahl-2026-wahlbezirke.csv").open() as stream:
        district_sum = sum(int(row["D3_4"]) for row in csv.DictReader(stream, delimiter=";"))
    assert actual["year"] == 2026
    assert actual["cdu_votes"] == district_sum == 34335
    assert actual["cdu_list_votes"] + actual["cdu_candidate_votes"] == actual["cdu_votes"]


def test_wahlarten_haben_explizite_nenner(result):
    for method in result["voting_methods"]:
        assert sum(c["votes"] for c in method["candidates"]) == method["finalist_votes"]
        assert method["finalist_votes"] < method["valid_votes"] <= method["voters"]
    postal = next(m for m in result["voting_methods"] if m["name"] == "Briefwahl")
    rohr = next(c for c in postal["candidates"] if c["slug"] == "rohr")
    assert round(rohr["share_all_pct"], 1) == 34.8
    assert round(analysis.percent(rohr["votes"], postal["finalist_votes"]), 1) == 51.1


def test_historische_gesamtwerte_statt_rueckkehrquoten(result):
    h14, h21 = result["history"]
    assert (h14["first"]["voters"], h14["runoff"]["voters"]) == (50801, 44149)
    assert h14["change_voters"] == -6652
    assert h14["voter_count_ratio_pct"] == pytest.approx(86.9057696)
    assert round(h14["turnout_change_pp"], 2) == -5.11
    assert (h21["first"]["voters"], h21["runoff"]["voters"]) == (72765, 81472)
    assert h21["change_voters"] == 8707
    assert round(h21["change_voters_pct"], 1) == 12.0
    assert round(h21["turnout_change_pp"], 2) == 6.47
    for h in result["history"]:
        for c in h["candidates"]:
            assert c["first_votes"] + c["change_votes"] == c["runoff_votes"]
            assert c["change_pct"] == pytest.approx((c["growth_factor"] - 1) * 100)


def test_fehlende_und_widerspruechliche_daten_sind_keine_nullwerte():
    assert analysis.percent(0, 0) is None
    assert analysis.percent(0, 10) == 0
    rows = analysis._read(analysis.REFERENCE / "praesentation-ob-wahlbezirke.json", analysis.NAMES)
    with pytest.raises(ValueError, match="fehlen"):
        analysis.totals([replace(rows[0], voters=None), *rows[1:]])
    with pytest.raises(ValueError, match="widersprechen"):
        analysis.totals([replace(rows[0], voters=10**9), *rows[1:]])


def test_unvollstaendige_quelle_wird_abgewiesen(tmp_path):
    path = tmp_path / "leer.json"
    path.write_text('{"tabelle":{"header":[],"zeilen":[]}}')
    with pytest.raises(ValueError, match="Unvollständiger"):
        analysis._read(path, analysis.NAMES)


def test_token_weiter_erforderlich(monkeypatch):
    monkeypatch.delenv("WAHLKAMPF_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        wahlabend.stichwahl_potenzial(token="irgendein-langer-test-token")
    assert exc.value.status_code == 404
    monkeypatch.setenv("WAHLKAMPF_TOKEN", "probe-token-fuer-die-browsertests")
    for token in [None, "", "falscher-test-token"]:
        with pytest.raises(HTTPException) as exc:
            wahlabend.stichwahl_potenzial(token=token)
        assert exc.value.status_code == 404


def test_http_vertrag_liefert_nur_die_neutrale_analyse(monkeypatch, result):
    monkeypatch.setenv("WAHLKAMPF_TOKEN", "probe-token-fuer-die-browsertests")
    response = TestClient(app).get("/api/wahlabend/stichwahl/potenzial", params={"token": "probe-token-fuer-die-browsertests"})
    assert response.status_code == 200
    assert response.json() == result  # Auch Felder, die FastAPI sonst still entfernt.
    assert not {"districts", "bundles", "assumptions", "projected_rohr", "strategy_counts"} & result.keys()
    schema = app.openapi()["paths"]["/api/wahlabend/stichwahl/potenzial"]["get"]
    assert [p["name"] for p in schema["parameters"]] == ["token"]
