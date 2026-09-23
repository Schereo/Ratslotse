"""Der Verlauf der Stichwahl (``history.record_mayor``, S3 aus
docs/plan-stichwahl-spannung.md): Punkte sammeln, entdoppeln, überleben —
und Führungswechsel erkennen.

Die Ratswahl hat dieselben Zusagen in ``test_wahlabend_verlauf.py``; hier
kommt dazu, was nur eine Mehrheitswahl hat: die Hochrechnung im Punkt und
die Frage, wer vorn liegt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "web" / "backend"))

from app.antworten import MayorHistoryPoint  # noqa: E402
from app.election import history, mayor  # noqa: E402
from app.routers import wahlabend as router  # noqa: E402

SLUG = "ob-stichwahl-2026"


def _punkt(at: str, n: int = 10, prange: float = 52.0, leader: str | None = "prange",
           proj: dict[str, float] | None = None) -> MayorHistoryPoint:
    return MayorHistoryPoint(at=at, reports_received=n, shares={"prange": prange, "rohr": round(100 - prange, 1)},
                             votes={"prange": round(prange * 100), "rohr": round((100 - prange) * 100)},
                             projected_shares=proj or {}, chance_pct=None, leader=leader, new_districts=[])


@pytest.fixture
def datei(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("WAHLABEND_HISTORY_FILE", str(tmp_path / "verlauf.json"))
    monkeypatch.setenv("FEATURE_FLAGS", "wahlabend")
    history.reset()
    mayor.reset()
    yield history.mayor_path(SLUG)
    history.reset()
    mayor.reset()


def test_die_stichwahl_hat_ihre_eigene_datei(datei):
    assert datei.name == f"verlauf-{SLUG}.json"
    assert datei != history.path()


def test_gleicher_stand_haengt_keinen_zweiten_punkt_an(datei):
    history.add_mayor(SLUG, _punkt("2026-09-27T16:10:00+00:00"))
    history.add_mayor(SLUG, _punkt("2026-09-27T16:11:00+00:00"))
    assert len(history.mayor_points(SLUG)) == 1
    history.add_mayor(SLUG, _punkt("2026-09-27T16:12:00+00:00", n=12))
    assert len(history.mayor_points(SLUG)) == 2
    # Eine neue Hochrechnung bei gleichem Ist ist ein neuer Punkt.
    history.add_mayor(SLUG, _punkt("2026-09-27T16:13:00+00:00", n=12, proj={"prange": 51.0, "rohr": 49.0}))
    assert len(history.mayor_points(SLUG)) == 3


def test_verlauf_uebersteht_den_neustart(datei):
    history.add_mayor(SLUG, _punkt("2026-09-27T16:10:00+00:00"))
    history.add_mayor(SLUG, _punkt("2026-09-27T16:20:00+00:00", n=20, prange=51.0))
    assert datei.is_file() and len(json.loads(datei.read_text(encoding="utf-8"))) == 2
    history.reset()
    punkte = history.mayor_points(SLUG)
    assert [p["reports_received"] for p in punkte] == [10, 20]
    assert punkte[1]["leader"] == "prange"


def test_kaputte_zeilen_werden_uebersprungen(datei):
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(json.dumps([{"at": "x"}, _punkt("2026-09-27T16:10:00+00:00"), "quatsch"]), encoding="utf-8")
    history.reset()
    assert len(history.mayor_points(SLUG)) == 1


def test_fuehrungswechsel_werden_erkannt():
    punkte = [
        _punkt("t1", 5, 48.0, "rohr"),
        _punkt("t2", 10, 50.0, None),     # Gleichstand: kein Wechsel
        _punkt("t3", 15, 51.0, "prange"),
        _punkt("t4", 20, 52.0, "prange"),
        _punkt("t5", 25, 49.5, "rohr"),
    ]
    w = history.lead_changes(punkte)
    assert [(x["at"], x["previous"], x["leader"]) for x in w] == [("t3", "rohr", "prange"), ("t5", "prange", "rohr")]
    assert w[0]["reports_received"] == 15
    assert history.lead_changes([]) == []


def test_wer_vorn_liegt():
    assert history.mayor_leader({}, {"a": 10, "b": 12}) == "b"
    assert history.mayor_leader({}, {"a": 10, "b": 10}) is None
    assert history.mayor_leader({}, {"a": None, "b": None}) is None


def test_live_vor_der_auszaehlung_haengt_nichts_an(datei):
    night = router.stichwahl(probe="1", counted=0)
    night["dataset"] = "live"
    assert history.record_mayor(SLUG, night) == []
    assert not datei.exists()


def test_der_live_punkt_traegt_hochrechnung_und_fuehrung(datei):
    night = router.stichwahl(probe="1", counted=60)
    punkte = history.record_mayor(SLUG, night)
    assert len(punkte) == 1
    p = punkte[0]
    assert p["reports_received"] == 60 and p["leader"] == "prange"
    assert p["votes"] == {c["slug"]: c["votes"] for c in night["candidates"]}
    assert set(p["projected_shares"]) == {"prange", "rohr"} and p["chance_pct"] is not None
    assert history.record_mayor(SLUG, night) == punkte, "derselbe Stand zweimal ist ein Punkt"


def test_die_probe_liefert_einen_verlauf_bis_zum_stand(datei):
    d = router.stichwahl(probe="1", counted=45)
    assert [p["reports_received"] for p in d["history"]] == [10, 20, 30, 40, 45]
    # Bezirk für Bezirk gezählt, führt in der Probe zuerst Rohr (die
    # Innenstadt meldet zuerst) — der Führungswechsel kommt um den 50. Bezirk.
    assert all(p["leader"] == "rohr" for p in d["history"])
    assert d["history"][0]["chance_pct"] is None and d["history"][-1]["chance_pct"] is not None
    assert d["lead_changes"] == []
    voll = router.stichwahl(probe="1", counted=None)
    assert voll["history"][-1]["leader"] == "prange" and voll["history"][-1]["reports_received"] == 133
    assert [(w["previous"], w["leader"], w["reports_received"]) for w in voll["lead_changes"]] == [("rohr", "prange", 50)]
    assert router.stichwahl(probe="1", counted=0)["history"] == []
    # Der erste Wahlgang trägt keinen Verlauf — sein Abend war die Ratswahl.
    e = router.ob_wahl(probe="1", counted=None)
    assert e["history"] == [] and e["lead_changes"] == []


def test_die_probe_der_stichwahl_zaehlt_bezirk_fuer_bezirk(datei):
    """Die Stadtzeile der Probe ist die Summe der gemeldeten Bezirke — wie
    live. Vorher war sie ein Anteil der Gesamtzahl, und der Verlauf eine
    Gerade: 52,1 % von der ersten bis zur letzten Minute."""
    from app.election import elections

    w = elections.runoff()
    stand = mayor.probe(60, w)
    gemeldet = [d for d in stand.districts if d.counted]
    assert stand.reports_received == len(gemeldet) == 60
    for c in stand.candidates:
        assert c.votes == sum(d.votes[c.slug] or 0 for d in gemeldet)
    anteile = {n: next(c.share_pct for c in mayor.probe(n, w).candidates if c.slug == "prange") for n in (30, 91, 133)}
    assert anteile[30] != anteile[133], "der Anteil bewegt sich über den Abend"
    assert anteile[91] > anteile[133], "nach 91 Urnenbezirken drückt die Briefwahl den Anteil"
    assert {c.slug: c.votes for c in mayor.probe(133, w).candidates} == {"prange": 28075, "rohr": 25850}


# ---------------------------------------------------------------- der Ticker (Tims Wunsch 23.09.2026)

def _live(n: int):
    """Ein Live-Stand mit ``n`` gezählten Bezirken — die Probe, umgeschrieben."""
    from app.election import elections

    night = router.stichwahl(probe="1", counted=n)
    night["dataset"] = "live"
    w = elections.runoff()
    return night, [d.number for d in mayor.probe(n, w).districts if d.counted]


def test_jeder_punkt_kennt_seine_neuen_bezirke_auch_nach_dem_neustart(datei):
    n10, z10 = _live(10)
    n25, z25 = _live(25)
    n40, z40 = _live(40)
    assert history.record_mayor(SLUG, n10, z10)[-1]["new_districts"] == sorted(z10)
    assert history.record_mayor(SLUG, n25, z25)[-1]["new_districts"] == sorted(set(z25) - set(z10))
    # Der Dienst startet neu: Was schon gemeldet war, weiß die Datei.
    history.reset()
    assert history.record_mayor(SLUG, n40, z40)[-1]["new_districts"] == sorted(set(z40) - set(z25))


def test_der_ticker_nennt_die_juengsten_bezirke_zuerst(datei):
    d = router.stichwahl(probe="1", counted=60)
    t = d["recent_districts"]
    assert len(t) == router.TICKER_MAX
    letzter = d["history"][-1]
    assert [z["number"] for z in t[: len(letzter["new_districts"])]] == sorted(letzter["new_districts"], reverse=True)[: len(t)]
    for z in t:
        assert round(sum(z["shares"].values()), 1) == 100.0
        assert z["leader"] == max(z["shares"], key=lambda s: z["shares"][s])
        assert set(z["first_round_shares"]) == {"prange", "rohr"}
    assert router.stichwahl(probe="1", counted=0)["recent_districts"] == []
