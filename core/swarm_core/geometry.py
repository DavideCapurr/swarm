"""Geometry primitives — geodesic math without pulling in heavy GIS at runtime.

We use a local equirectangular approximation for short distances (<10 km is
typical for the wedge: private property scale). For anything larger we delegate to
`pyproj`/`shapely` in the orchestrator. Keeping the hot path light here.
"""

from __future__ import annotations

import math

from swarm_core.messages import Geo

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(a: Geo, b: Geo) -> float:
    """Great-circle distance between two points, ignoring altitude. Meters."""

    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlon = math.radians(b.lon - a.lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def euclidean_m(a: Geo, b: Geo) -> float:
    """3D distance including altitude. Approximates haversine for short ranges."""

    flat = haversine_m(a, b)
    dz = b.alt_m - a.alt_m
    return math.sqrt(flat * flat + dz * dz)


def midpoint(a: Geo, b: Geo) -> Geo:
    """Approximate midpoint (good enough for sub-km ranges)."""

    return Geo(lat=(a.lat + b.lat) / 2, lon=(a.lon + b.lon) / 2, alt_m=(a.alt_m + b.alt_m) / 2)


def bbox(points: list[Geo]) -> tuple[Geo, Geo]:
    """South-west and north-east corners of the bounding box."""

    if not points:
        raise ValueError("bbox: empty point list")
    sw = Geo(
        lat=min(p.lat for p in points),
        lon=min(p.lon for p in points),
        alt_m=min(p.alt_m for p in points),
    )
    ne = Geo(
        lat=max(p.lat for p in points),
        lon=max(p.lon for p in points),
        alt_m=max(p.alt_m for p in points),
    )
    return sw, ne


def point_in_polygon(p: Geo, polygon: list[Geo]) -> bool:
    """Ray-casting test in (lon, lat) space. Adequate for short distances."""

    if len(polygon) < 3:
        return False
    inside = False
    x, y = p.lon, p.lat
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i].lon, polygon[i].lat
        xj, yj = polygon[j].lon, polygon[j].lat
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def centroid(polygon: list[Geo]) -> Geo:
    """Arithmetic centroid of a polygon's vertices.

    Good enough for the sector grid: rectangles' arithmetic centroid coincides
    with the geometric centroid. For irregular polygons later, swap in
    shapely.centroid.
    """
    if not polygon:
        raise ValueError("centroid: empty polygon")
    n = len(polygon)
    return Geo(
        lat=sum(p.lat for p in polygon) / n,
        lon=sum(p.lon for p in polygon) / n,
        alt_m=sum(p.alt_m for p in polygon) / n,
    )


def sector_grid(center: Geo, half_extent_m: float, n: int) -> list[list[Geo]]:
    """NxN square sector grid centered on `center`, half-side `half_extent_m`.

    Returns a list of `n*n` polygons. Each polygon is the 4 corner `Geo`s in
    CCW order (SW, SE, NE, NW). Local equirectangular approximation —
    accurate enough for the demo wedge (<10 km extent). For larger or
    higher-precision needs we delegate to pyproj/shapely.

    Cell size on Earth's surface ≈ `2 * half_extent_m / n` meters per side.
    """
    if n <= 0:
        raise ValueError(f"sector_grid: n must be > 0, got {n}")
    if half_extent_m <= 0:
        raise ValueError(f"sector_grid: half_extent_m must be > 0, got {half_extent_m}")

    # Meters → degrees at this latitude. lat-degree is ~constant; lon-degree
    # shrinks with cos(lat).
    lat_rad = math.radians(center.lat)
    cos_lat = max(math.cos(lat_rad), 1e-6)  # avoid /0 at poles
    deg_per_m_lat = 1.0 / (EARTH_RADIUS_M * math.pi / 180.0)
    deg_per_m_lon = deg_per_m_lat / cos_lat

    half_lat_deg = half_extent_m * deg_per_m_lat
    half_lon_deg = half_extent_m * deg_per_m_lon
    cell_lat_deg = (2 * half_lat_deg) / n
    cell_lon_deg = (2 * half_lon_deg) / n

    sw_lat = center.lat - half_lat_deg
    sw_lon = center.lon - half_lon_deg

    sectors: list[list[Geo]] = []
    for row in range(n):
        for col in range(n):
            lat0 = sw_lat + row * cell_lat_deg
            lat1 = lat0 + cell_lat_deg
            lon0 = sw_lon + col * cell_lon_deg
            lon1 = lon0 + cell_lon_deg
            sectors.append(
                [
                    Geo(lat=lat0, lon=lon0),
                    Geo(lat=lat0, lon=lon1),
                    Geo(lat=lat1, lon=lon1),
                    Geo(lat=lat1, lon=lon0),
                ]
            )
    return sectors


def closest_sector(p: Geo, sectors: list[list[Geo]]) -> int | None:
    """Return the index of the sector whose centroid is closest to `p`.

    `None` if `sectors` is empty. Ties broken by lower index. Containment is
    *not* a precondition — the point can be outside all sectors and the
    closest-centroid one is still returned.
    """
    if not sectors:
        return None
    best_idx = 0
    best_d = haversine_m(p, centroid(sectors[0]))
    for i in range(1, len(sectors)):
        d = haversine_m(p, centroid(sectors[i]))
        if d < best_d:
            best_d = d
            best_idx = i
    return best_idx


def tile_polygon(polygon: list[Geo], slices: int) -> list[list[Geo]]:
    """Naive vertical slicing of a convex-ish polygon for COVER decomposition.

    For commit 1 this is intentionally simple: split the bbox into `slices`
    longitudinal strips and intersect with the polygon by clipping to bbox.
    Good enough for demos; later commits can swap for proper Voronoi or
    capacity-constrained partitioning.
    """

    if slices <= 0:
        raise ValueError("slices must be > 0")
    sw, ne = bbox(polygon)
    step = (ne.lon - sw.lon) / slices
    tiles: list[list[Geo]] = []
    for k in range(slices):
        lon0 = sw.lon + k * step
        lon1 = sw.lon + (k + 1) * step
        tile = [
            Geo(lat=sw.lat, lon=lon0),
            Geo(lat=sw.lat, lon=lon1),
            Geo(lat=ne.lat, lon=lon1),
            Geo(lat=ne.lat, lon=lon0),
        ]
        tiles.append(tile)
    return tiles
