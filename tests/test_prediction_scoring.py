"""Die Punkte-Formel des Tippspiels (docs/plan-tippspiel-ratswahl.md, Anhang A).

Reine Funktionen, kein Netz, keine Datenbank — genau das macht sie hier
testbar ohne jede Fixture.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web" / "backend"))

from app.prediction import scoring  # noqa: E402
from app.prediction.scoring import Standing, order, score, seat_points  # noqa: E402


# ------------------------------------------------------------------ seat_points

@pytest.mark.parametrize("tip, actual, erwartet", [
    (14, 14, 5),    # exakt
    (0, 0, 5),      # 0 auf 0 IST exakt — sonst wären kleine Listen wertlos
    (14, 15, 3),    # ±1
    (15, 14, 3),
    (14, 16, 1),    # ±2
    (16, 14, 1),
    (14, 17, 0),    # ±3 und mehr
    (14, 11, 0),
    (0, 3, 0),
])
def test_seat_points_stufen(tip, actual, erwartet):
    assert seat_points(tip, actual) == erwartet


def test_seat_points_ohne_amtliche_zahl_ist_null():
    assert seat_points(14, None) == 0
    assert seat_points(0, None) == 0


# ------------------------------------------------------------------ mayor_points

@pytest.mark.parametrize("tip, actual, erwartet", [
    (30.0, 30.0, 6),
    (30.0, 30.5, 6),    # Grenze gehört zur besseren Stufe
    (30.0, 29.5, 6),
    (30.0, 31.5, 3),    # Grenze der 3er-Stufe
    (30.0, 28.5, 3),
    (30.0, 33.0, 1),    # Grenze der 1er-Stufe
    (30.0, 27.0, 1),
    (30.0, 33.1, 0),
    (30.0, 26.9, 0),
])
def test_mayor_points_stufen(tip, actual, erwartet):
    assert scoring.mayor_points(tip, actual) == erwartet


def test_mayor_points_ohne_amtliche_zahl_ist_null():
    assert scoring.mayor_points(30.0, None) == 0


# ------------------------------------------------------------------ score()

def test_score_summiert_ueber_alle_listen():
    tip_seats = {"spd": 14, "cdu": 12, "gruene": 8}
    actual = {"spd": 14, "cdu": 13, "gruene": 6}
    s = score(tip_seats, None, actual, {})
    assert s.seat_points == 5 + 3 + 1   # exakt, ±1, ±2 (|8-6|=2 → 1 Punkt)
    assert s.exact_lists == 1
    assert s.deviation == 0 + 1 + 2
    assert s.mayor_points == 0
    assert s.total == s.seat_points


def test_score_ohne_ob_tipp_gibt_null_bonus_kein_abzug():
    s_ohne = score({"spd": 14}, None, {"spd": 14}, {"rohr": 30.0})
    s_mit_daneben = score({"spd": 14}, {"rohr": 90.0}, {"spd": 14}, {"rohr": 30.0})
    assert s_ohne.mayor_points == 0
    assert s_mit_daneben.mayor_points == 0
    assert s_ohne.total == s_mit_daneben.total == s_ohne.seat_points


def test_score_ob_bonus_zaehlt_je_kandidatur():
    tip_mayor = {"rohr": 30.0, "prange": 40.0}
    actual_mayor = {"rohr": 30.2, "prange": 20.0}
    s = score({}, tip_mayor, {}, actual_mayor)
    assert s.mayor_points == 6 + 0   # rohr exakt genug, prange 20 Punkte daneben
    assert s.total == s.mayor_points


def test_score_deviation_ist_none_ohne_jede_amtliche_zahl():
    s = score({"spd": 14, "cdu": 12}, None, {}, {})
    assert s.deviation is None
    assert s.seat_points == 0


def test_score_deviation_wird_zur_zahl_sobald_eine_liste_feststeht():
    s = score({"spd": 14, "cdu": 12}, None, {"spd": 14}, {})
    assert s.deviation == 0  # nur SPD zählt, Abweichung 0


def test_score_hoechstwerte():
    alle_16 = {f"liste{i}": 0 for i in range(16)}
    alle_9 = {f"ob{i}": 30.0 for i in range(9)}
    s = score(alle_16, alle_9, alle_16, alle_9)
    assert s.seat_points == scoring.MAX_SEAT_POINTS == 80
    assert s.mayor_points == scoring.MAX_MAYOR_POINTS == 54
    assert s.total == scoring.MAX_TOTAL_POINTS == 134


# ------------------------------------------------------------------ order() / ranks()

def _standing(id_: int, name: str, total: int, deviation: int | None = 0,
             updated_at: str = "2026-09-13T20:00:00", scored: bool = True) -> Standing:
    s = score({"spd": 0}, None, {"spd": 0}, {})  # Platzhalter, wird gleich ersetzt
    from dataclasses import replace
    s = replace(s, total=total, deviation=deviation)
    return Standing(id=id_, name=name, updated_at=updated_at, scored=scored, score=s)


def test_order_sortiert_nach_punkten_absteigend():
    rows = [_standing(1, "Anna", 50), _standing(2, "Bert", 80), _standing(3, "Cara", 60)]
    assert [r.id for r in order(rows)] == [2, 3, 1]


def test_order_gleichstand_entscheidet_abweichung():
    rows = [_standing(1, "Anna", 60, deviation=5), _standing(2, "Bert", 60, deviation=2)]
    assert [r.id for r in order(rows)] == [2, 1]


def test_order_gleichstand_und_gleiche_abweichung_entscheidet_abgabezeit():
    rows = [
        _standing(1, "Anna", 60, deviation=2, updated_at="2026-09-13T20:05:00"),
        _standing(2, "Bert", 60, deviation=2, updated_at="2026-09-13T19:58:00"),
    ]
    assert [r.id for r in order(rows)] == [2, 1]   # Bert war früher fertig


def test_order_spaetstarter_stehen_geschlossen_hinten():
    rows = [
        _standing(1, "Anna", 40, scored=True),
        _standing(2, "Zoe", 200, scored=False),   # Spätstarter mit Bestpunktzahl
        _standing(3, "Bert", 60, scored=True),
    ]
    assert [r.id for r in order(rows)] == [3, 1, 2]


def test_order_ohne_amtliche_zahl_zaehlt_als_schlechteste_abweichung():
    rows = [_standing(1, "Anna", 0, deviation=None), _standing(2, "Bert", 0, deviation=3)]
    assert [r.id for r in order(rows)] == [2, 1]


def test_ranks_ist_dicht_und_beginnt_bei_eins():
    """Name ist der letzte Tie-Breaker, also gibt es nie einen echten
    Gleichstand — jede Person bekommt einen eigenen, lückenlosen Rang."""
    rows = [_standing(1, "Anna", 50), _standing(2, "Bert", 80), _standing(3, "Cara", 80)]
    r = scoring.ranks(rows)
    assert sorted(r.values()) == [1, 2, 3]
    assert r[2] == 1 and r[3] == 2 and r[1] == 3  # Bert vor Cara (Namen-Tie-Breaker), Anna zuletzt
