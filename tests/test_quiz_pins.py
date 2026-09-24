"""„Wo liegt das?" (council.quiz_pins): Entfernung zur Geometrie, Punkte."""
from __future__ import annotations

import pytest

from council import quiz_pins as qp

# Ein Straßenstück in Oldenburg, west–ost auf 53,14° N.
LINE = {"type": "LineString", "coordinates": [[8.20, 53.14], [8.22, 53.14]]}
AREA = {"type": "Polygon", "coordinates": [[[8.20, 53.14], [8.22, 53.14], [8.22, 53.15], [8.20, 53.15], [8.20, 53.14]]]}


def test_on_the_line_is_zero():
    assert qp.distance_m(LINE, 53.14, 8.21) == pytest.approx(0, abs=1)


def test_north_of_the_line_in_metres():
    # 0,005° Breite ≈ 553 m
    assert qp.distance_m(LINE, 53.145, 8.21) == pytest.approx(553, rel=0.05)


def test_beyond_the_end_measures_to_the_end():
    # 0,01° Länge auf 53,14° N ≈ 668 m hinter dem östlichen Ende
    assert qp.distance_m(LINE, 53.14, 8.23) == pytest.approx(668, rel=0.05)


def test_inside_an_area_is_zero_outside_to_its_edge():
    assert qp.distance_m(AREA, 53.145, 8.21) == 0
    assert qp.distance_m(AREA, 53.155, 8.21) == pytest.approx(553, rel=0.05)


def test_multilinestring_takes_the_nearest_part():
    multi = {"type": "MultiLineString", "coordinates": [
        [[8.10, 53.10], [8.11, 53.10]], LINE["coordinates"]]}
    assert qp.distance_m(multi, 53.14, 8.21) == pytest.approx(0, abs=1)


def test_unknown_geometry_is_none():
    assert qp.distance_m({"type": "GeometryCollection", "geometries": []}, 53.14, 8.21) is None


@pytest.mark.parametrize("dist,points", [(0, 3), (150, 3), (151, 2), (500, 2), (1500, 1), (1501, 0)])
def test_points_steps(dist, points):
    assert qp.points_for(dist) == points


def test_describe():
    assert qp.describe(5) == "genau drauf"
    assert qp.describe(377) == "380 m daneben"
    assert qp.describe(1432) == "1,4 km daneben"
