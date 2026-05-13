from __future__ import annotations

import math

import pytest

from swarm_core.geometry import (
    bbox,
    euclidean_m,
    haversine_m,
    midpoint,
    point_in_polygon,
    tile_polygon,
)
from swarm_core.messages import Geo


def test_haversine_zero_distance() -> None:
    g = Geo(lat=45.0, lon=10.0)
    assert haversine_m(g, g) == pytest.approx(0.0, abs=1e-6)


def test_haversine_one_degree_latitude_is_about_111km() -> None:
    a = Geo(lat=45.0, lon=10.0)
    b = Geo(lat=46.0, lon=10.0)
    d = haversine_m(a, b)
    assert 110_000 < d < 112_000


def test_euclidean_includes_altitude() -> None:
    a = Geo(lat=45.0, lon=10.0, alt_m=0.0)
    b = Geo(lat=45.0, lon=10.0, alt_m=100.0)
    assert euclidean_m(a, b) == pytest.approx(100.0, abs=1e-3)


def test_midpoint_basic() -> None:
    m = midpoint(Geo(lat=0.0, lon=0.0), Geo(lat=10.0, lon=20.0, alt_m=100))
    assert m.lat == 5.0
    assert m.lon == 10.0
    assert m.alt_m == 50.0


def test_bbox_handles_multiple_points() -> None:
    sw, ne = bbox(
        [
            Geo(lat=45.0, lon=10.0),
            Geo(lat=46.0, lon=11.0),
            Geo(lat=45.5, lon=10.5, alt_m=100),
        ]
    )
    assert sw.lat == 45.0 and sw.lon == 10.0
    assert ne.lat == 46.0 and ne.lon == 11.0


def test_bbox_raises_on_empty() -> None:
    with pytest.raises(ValueError):
        bbox([])


def test_point_in_polygon_square() -> None:
    square = [
        Geo(lat=0.0, lon=0.0),
        Geo(lat=1.0, lon=0.0),
        Geo(lat=1.0, lon=1.0),
        Geo(lat=0.0, lon=1.0),
    ]
    assert point_in_polygon(Geo(lat=0.5, lon=0.5), square)
    assert not point_in_polygon(Geo(lat=2.0, lon=2.0), square)


def test_tile_polygon_partitions_bbox_into_slices() -> None:
    poly = [
        Geo(lat=45.0, lon=10.0),
        Geo(lat=45.1, lon=10.0),
        Geo(lat=45.1, lon=10.1),
        Geo(lat=45.0, lon=10.1),
    ]
    tiles = tile_polygon(poly, slices=3)
    assert len(tiles) == 3
    # Tiles should cover the full longitudinal range when stitched together.
    leftmost = min(t[0].lon for t in tiles)
    rightmost = max(t[1].lon for t in tiles)
    assert math.isclose(leftmost, 10.0, abs_tol=1e-9)
    assert math.isclose(rightmost, 10.1, abs_tol=1e-9)


def test_tile_polygon_rejects_zero_slices() -> None:
    with pytest.raises(ValueError):
        tile_polygon([Geo(lat=0, lon=0), Geo(lat=1, lon=0), Geo(lat=0, lon=1)], slices=0)
