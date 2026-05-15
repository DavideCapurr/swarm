"""Tests for the sector grid + closest-sector helpers added in Phase 0."""

from __future__ import annotations

import math

import pytest

from swarm_core.geometry import (
    centroid,
    closest_sector,
    haversine_m,
    point_in_polygon,
    sector_grid,
)
from swarm_core.messages import Geo

VINEYARD = Geo(lat=44.7, lon=8.03)


def test_sector_grid_count_matches_n_squared() -> None:
    sectors = sector_grid(VINEYARD, half_extent_m=500.0, n=4)
    assert len(sectors) == 16


def test_sector_grid_covers_center() -> None:
    """With odd N the center is strictly inside one sector; with even N it
    sits on the boundary of 4 cells. Both are correct — we assert >= 1."""
    sectors = sector_grid(VINEYARD, half_extent_m=500.0, n=3)
    hits = sum(1 for s in sectors if point_in_polygon(VINEYARD, s))
    assert hits == 1, f"center should land in exactly one sector for odd N, got {hits}"


def test_sector_grid_cell_size_close_to_target() -> None:
    """For n=2, each cell is half the total extent on each side."""
    half = 1000.0
    n = 2
    sectors = sector_grid(VINEYARD, half_extent_m=half, n=n)
    # Diagonal of the first cell ≈ sqrt(2) * (2*half/n).
    p0 = sectors[0][0]  # SW
    p2 = sectors[0][2]  # NE
    diag = haversine_m(p0, p2)
    expected = math.sqrt(2) * (2 * half / n)
    # 5% tolerance — small-angle approximation.
    assert abs(diag - expected) / expected < 0.05


def test_sector_grid_rejects_invalid_args() -> None:
    with pytest.raises(ValueError):
        sector_grid(VINEYARD, half_extent_m=500.0, n=0)
    with pytest.raises(ValueError):
        sector_grid(VINEYARD, half_extent_m=-1.0, n=4)


def test_closest_sector_returns_none_for_empty() -> None:
    assert closest_sector(VINEYARD, []) is None


def test_closest_sector_returns_center_cell() -> None:
    sectors = sector_grid(VINEYARD, half_extent_m=500.0, n=3)
    # For n=3 the center is in cell index 4 (middle row, middle col).
    assert closest_sector(VINEYARD, sectors) == 4


def test_closest_sector_handles_outside_point() -> None:
    """A point outside the grid still resolves to the nearest cell."""
    sectors = sector_grid(VINEYARD, half_extent_m=500.0, n=3)
    far_north = Geo(lat=VINEYARD.lat + 0.5, lon=VINEYARD.lon)
    idx = closest_sector(far_north, sectors)
    assert idx is not None
    # Should map to one of the northern row (indices 6, 7, 8 in row-major).
    assert idx in {6, 7, 8}


def test_centroid_of_square_is_mean() -> None:
    square = [Geo(lat=0, lon=0), Geo(lat=0, lon=1), Geo(lat=1, lon=1), Geo(lat=1, lon=0)]
    c = centroid(square)
    assert c.lat == pytest.approx(0.5)
    assert c.lon == pytest.approx(0.5)


def test_centroid_rejects_empty() -> None:
    with pytest.raises(ValueError):
        centroid([])
