"""Tests for the geofence helpers added in Phase 6.A."""

from __future__ import annotations

from swarm_core.geometry import (
    path_within_polygon,
    point_in_polygon,
    segment_crosses_polygon_boundary,
)
from swarm_core.messages import Geo

SQUARE = [
    Geo(lat=0.0, lon=0.0),
    Geo(lat=0.0, lon=1.0),
    Geo(lat=1.0, lon=1.0),
    Geo(lat=1.0, lon=0.0),
]

CONCAVE = [
    Geo(lat=0.0, lon=0.0),
    Geo(lat=0.0, lon=2.0),
    Geo(lat=0.7, lon=2.0),
    Geo(lat=0.7, lon=1.0),
    Geo(lat=1.3, lon=1.0),
    Geo(lat=1.3, lon=2.0),
    Geo(lat=2.0, lon=2.0),
    Geo(lat=2.0, lon=0.0),
]  # square [0,2]x[0,2] with a rectangular notch at lon in (1,2), lat in (0.7,1.3)


def test_segment_inside_square_does_not_cross_boundary() -> None:
    assert (
        segment_crosses_polygon_boundary(
            Geo(lat=0.25, lon=0.25), Geo(lat=0.75, lon=0.75), SQUARE
        )
        is False
    )


def test_segment_with_one_endpoint_outside_crosses() -> None:
    assert (
        segment_crosses_polygon_boundary(
            Geo(lat=0.5, lon=0.5), Geo(lat=0.5, lon=1.5), SQUARE
        )
        is True
    )


def test_segment_through_concave_notch_detected() -> None:
    """Both endpoints inside the C-shape but the segment cuts across the
    notch (concave interior). The boundary-crossing check catches this;
    a naive "both-endpoints-inside" check would miss it."""

    a = Geo(lat=0.5, lon=1.5)
    b = Geo(lat=1.5, lon=1.5)
    assert point_in_polygon(a, CONCAVE)
    assert point_in_polygon(b, CONCAVE)
    assert segment_crosses_polygon_boundary(a, b, CONCAVE) is True


def test_path_within_polygon_happy_path() -> None:
    waypoints = [
        Geo(lat=0.1, lon=0.1),
        Geo(lat=0.4, lon=0.3),
        Geo(lat=0.7, lon=0.6),
    ]
    assert path_within_polygon(waypoints, SQUARE) is True


def test_path_within_polygon_rejects_outside_waypoint() -> None:
    waypoints = [
        Geo(lat=0.1, lon=0.1),
        Geo(lat=2.0, lon=2.0),
    ]
    assert path_within_polygon(waypoints, SQUARE) is False


def test_path_within_polygon_rejects_concave_shortcut() -> None:
    waypoints = [Geo(lat=0.5, lon=1.5), Geo(lat=1.5, lon=1.5)]
    assert path_within_polygon(waypoints, CONCAVE) is False


def test_path_within_polygon_fails_closed_on_empty() -> None:
    assert path_within_polygon([], SQUARE) is False
    assert path_within_polygon([Geo(lat=0.5, lon=0.5)], []) is False


def test_path_within_polygon_single_waypoint() -> None:
    assert path_within_polygon([Geo(lat=0.5, lon=0.5)], SQUARE) is True
    assert path_within_polygon([Geo(lat=2.0, lon=2.0)], SQUARE) is False
