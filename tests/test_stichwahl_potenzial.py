"""Das Potenzial-Modell der Stichwahl (``web/backend/app/election/potential.py``)
und sein Endpunkt hinter dem Token.

Die Zahlen hier sind die aus ``docs/plan-stichwahl-potenzial.md``. Fällt ein
Test, stimmt der Plan nicht mehr — dann ist der Plan zu korrigieren, nicht
der Test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.election import potential  # noqa: E402
from app.routers import wahlabend as router  # noqa: E402


@pytest.fixture(scope="module")
def vorgabe():
    return potential.compute()


def test_die_ausgangslage_2026(vorgabe):
    p = vorgabe
    assert p["rohr"] == 25850 and p["prange"] == 28075 and p["lead"] == 2225
    # Alle sieben Ausgeschiedenen: fünf benannt, Castur und Stille als „Sonstige" (1.509).
    assert p["pool"] == 10198 + 4945 + 6211 + 4025 + 3843 + 1509 == 30731
    assert len(p["districts"]) == 133
    assert all(z["eligible"] > 0 for z in p["districts"] if not z["postal"])
    assert all(z["non_voters"] == 0 and z["strategy"] == "postal" for z in p["districts"] if z["postal"])


def test_die_ratswahl_2026_und_nicht_die_generalprobe(vorgabe):
    """Die Prüfung vom 16.09.2026 (Codex) fand 37.430 CDU-Stimmen — das war
    2021, aus der Generalprobe. 2026 sind es 34.335, und das sind Stimmen,
    keine Personen: bis zu drei je Wählendem (2,91 im Schnitt)."""
    p = vorgabe
    assert p["cdu_council"] == 34335
    assert p["votes_per_voter"] == 2.91
    assert abs(p["cdu_voters_est"] - round(34335 / 2.91)) <= 60   # Rundung je Bezirk
    assert p["cdu_voters_est"] == sum(z["cdu_voters_est"] for z in p["districts"])


def test_nichtwaehlende_ohne_die_briefwaehlenden(vorgabe):
    """Dieselbe Prüfung: 76.873 „Nichtwählende an der Urne" enthielten die
    27.351 Briefwählenden. Stadtweit sind es Wahlberechtigte minus Wählende
    (Urne + Brief) = 49.522; je Bezirk geschätzt über die dort ausgestellten
    Wahlscheine, deshalb ein paar Stimmen Rundung."""
    p = vorgabe
    assert p["eligible"] == 135513 and p["voters"] == 85991
    assert abs(p["non_voters"] - (p["eligible"] - p["voters"])) <= 10
    assert p["non_voters"] == sum(z["non_voters"] for z in p["districts"])
    urne = [z for z in p["districts"] if not z["postal"]]
    assert all(0 <= z["non_voters"] <= z["eligible"] - z["voters"] for z in urne)
    assert sum(z["ballot_papers"] for z in urne) == 30458


def test_die_briefwahl_ist_rohrs_bessere_haelfte(vorgabe):
    assert vorgabe["rohr_pct_postal"] > vorgabe["rohr_pct_urn"] + 4
    assert vorgabe["rohr_pct_urn"] == 46.3 and vorgabe["rohr_pct_postal"] == 51.1


def test_null_heisst_null_und_die_regler_wirken_linear():
    null = potential.compute(potential.Regler(transfers={s: (0, 0) for s in potential.VORGABE}, cdu=(0, 0)))
    assert null["net_total"] == 0 and null["balance"] == -null["lead"]
    nur_linke = potential.compute(potential.Regler(
        transfers={**{s: (0, 0) for s in potential.VORGABE}, "boldt": (100, 0)}, cdu=(0, 0)))
    assert nur_linke["net_total"] == 10198
    # Beteiligung: 90 % der Rohr-Basis kostet ein Zehntel seiner Stimmen —
    # bis auf die Rundung je Bezirk (133 × höchstens eine halbe Stimme).
    weniger = potential.compute(potential.Regler(transfers={s: (0, 0) for s in potential.VORGABE}, cdu=(0, 0), turnout_rohr=90))
    assert abs(weniger["balance"] - (-weniger["lead"] - 2585)) <= 67


def test_mit_den_vorgaben_steht_rohr_vorn(vorgabe):
    """Der Plan sagt „+5.211 netto, Saldo rund +3.000" — Rundung je Bezirk
    erlaubt ein paar Stimmen Abweichung, nicht mehr."""
    assert abs(vorgabe["net_total"] - 5211) <= 5
    assert 2900 <= vorgabe["balance"] <= 3050


def test_jeder_urnenbezirk_hat_einen_ort_und_eine_strategie(vorgabe):
    urne = [z for z in vorgabe["districts"] if not z["postal"]]
    assert all(z["district_name"] != "Briefwahl" for z in urne)
    assert {z["strategy"] for z in urne} <= {"hold", "persuade", "both", "skip"}
    # Die Hochburg mit großem Pool ist „both“, die Diaspora mit kleinem Ertrag „skip“.
    by = {z["number"]: z for z in urne}
    assert by[203]["strategy"] == "both", by[203]   # Kulturzentrum PFL, Innenstadt
    assert by[501]["strategy"] == "skip", by[501]   # Caritas, Bümmerstede
    assert sum(vorgabe["strategy_counts"].values()) == 133


def test_die_buendel_summieren_die_bezirke(vorgabe):
    b = {x["district_name"]: x for x in vorgabe["bundles"]}
    assert b["Eversten"]["districts"] == 13
    assert vorgabe["bundles"][0]["district_name"] == "Eversten"
    urne = [z for z in vorgabe["districts"] if not z["postal"]]
    assert sum(x["eligible"] for x in vorgabe["bundles"]) == sum(z["eligible"] for z in urne)


def test_2021_ist_gemessen_und_gewarnt(vorgabe):
    l = vorgabe["lessons_2021"]
    assert l["voters_first"] == 72765 and l["voters_runoff"] == 81472
    assert l["fuhrhop_growth_by_fifth"][0] > l["fuhrhop_growth_by_fifth"][-1] > 1.5
    assert l["fuhrhop_pct_postal_runoff"] > l["fuhrhop_pct_urn_runoff"]
    assert "Bundestagswahl" in l["note"]
    assert any("Bundestagswahl" in c for c in vorgabe["caveats"])


def test_2014_ist_die_gegenprobe_ohne_bundestagswahl(vorgabe):
    """Krogmann gegen Baak, 28.09./12.10.2014 — die Zahlen der Open-Data-CSVs
    des Votemanagers (Gesamtergebnis: 50.801 → 44.149 Wählende)."""
    l = vorgabe["lessons_2014"]
    assert l["voters_first"] == 50801 and l["voters_runoff"] == 44149
    assert l["return_rate_pct"] == 86.9
    assert l["krogmann_first"] == 23482 and l["krogmann_runoff"] == 30005
    assert l["baak_first"] == 12603 and l["baak_runoff"] == 13348
    assert l["eliminated_first"] == 11129 + 3193
    # Die Beteiligung hielt in Krogmanns Hochburgen besser als in Baaks — und
    # der Sieger wuchs dort am stärksten, wo er schwach war (wie Fuhrhop 2021).
    assert l["return_by_fifth"][-1] > l["return_by_fifth"][0]
    assert l["krogmann_growth_by_fifth"][0] > l["krogmann_growth_by_fifth"][-1] > 1
    assert len(l["return_by_fifth"]) == len(l["baak_growth_by_fifth"]) == 5
    assert "12. Oktober 2014" in l["note"]
    # Je Kandidat sein schwächstes und stärkstes Fünftel — absolut, aus #1387:
    # Krogmann +1.534 in den schwachen, +711 in den starken; Baak +427 / −102.
    assert l["krogmann_strength"]["weak"] == {"districts": 18, "first": 3051, "runoff": 4585, "change": 1534, "change_pct": 50.3}
    assert l["krogmann_strength"]["strong"] == {"districts": 18, "first": 4881, "runoff": 5592, "change": 711, "change_pct": 14.6}
    assert l["baak_strength"]["weak"]["change"] == 427 and l["baak_strength"]["strong"]["change"] == -102


# ---------------------------------------------------------------- der Endpunkt

def _ruf(**kw):
    args = dict(token=None, boldt=None, kuessner=None, butzin=None, froehlich=None, wilkens=None, others=None, cdu=None,
                turnout_rohr=100, turnout_prange=100, turnout_pool=100)
    args.update(kw)
    return router.stichwahl_potenzial(**args)


def test_ohne_token_gibt_es_die_seite_nicht(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    monkeypatch.delenv("WAHLKAMPF_TOKEN", raising=False)
    with pytest.raises(HTTPException) as e:
        _ruf(token="irgendwas-langes-und-falsches")
    assert e.value.status_code == 404
    monkeypatch.setenv("WAHLKAMPF_TOKEN", "richtig-und-lang-genug-1234")
    for falsch in (None, "", "falsch-und-lang-genug-1234"):
        with pytest.raises(HTTPException) as e:
            _ruf(token=falsch)
        assert e.value.status_code == 404
    # Ein zu kurzer Token in der .env zählt als nicht gesetzt.
    monkeypatch.setenv("WAHLKAMPF_TOKEN", "kurz")
    with pytest.raises(HTTPException):
        _ruf(token="kurz")


def test_ohne_eigenen_token_zaehlt_der_aus_dem_jwt_geheimnis(monkeypatch):
    """Kein neuer Eintrag in der .env nötig: Ohne WAHLKAMPF_TOKEN leitet sich
    der Token aus WEB_JWT_SECRET ab — deterministisch, 24 Zeichen, und nie
    aus dem unsicheren Vorgabewert."""
    from fastapi import HTTPException

    from app.config import get_settings

    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    monkeypatch.delenv("WAHLKAMPF_TOKEN", raising=False)
    monkeypatch.setattr(get_settings(), "web_jwt_secret", "ein-geheimnis-fuer-den-test")
    abgeleitet = router.wahlkampf_token()
    assert abgeleitet and len(abgeleitet) == 24 and abgeleitet == router.wahlkampf_token()
    assert _ruf(token=abgeleitet)["lead"] == 2225
    monkeypatch.setenv("WAHLKAMPF_TOKEN", "eigener-token-lang-genug-1234")
    assert router.wahlkampf_token() == "eigener-token-lang-genug-1234"
    with pytest.raises(HTTPException):
        _ruf(token=abgeleitet)
    monkeypatch.delenv("WAHLKAMPF_TOKEN")
    monkeypatch.setattr(get_settings(), "web_jwt_secret", "dev-insecure-change-me")
    assert router.wahlkampf_token() is None


def test_mit_token_kommt_die_rechnung_und_die_regler_greifen(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    monkeypatch.setenv("WAHLKAMPF_TOKEN", "richtig-und-lang-genug-1234")
    p = _ruf(token="richtig-und-lang-genug-1234")
    assert p["lead"] == 2225 and abs(p["net_total"] - 5211) <= 5
    q = _ruf(token="richtig-und-lang-genug-1234", boldt="80,5", cdu="40,10", turnout_prange=95)
    assert q["assumptions"][0]["to_rohr"] == 80 and q["cdu_to_rohr"] == 40 and q["turnout_prange"] == 95
    assert q["balance"] > p["balance"]
    with pytest.raises(HTTPException) as e:
        _ruf(token="richtig-und-lang-genug-1234", boldt="70,40")
    assert e.value.status_code == 422
