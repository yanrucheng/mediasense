"""Offline service-region evidence, independent of the executing machine's network."""

from functools import lru_cache
import hashlib
from importlib.resources import files
import json
from math import cos, radians

from .model import GeoCoordinate, MapDatum

BOUNDARY_SHA256 = "25aca3d92c8b53faf03021601b344f58277577d71f6d63e3d55ea363ed6b257c"
BOUNDARY_GUARD_METERS = 500


@lru_cache(maxsize=1)
def _boundaries():
    raw = (
        files("mediasense")
        .joinpath("_resources/geo/ne-regions-5.1.1.json")
        .read_bytes()
    )
    if hashlib.sha256(raw).hexdigest() != BOUNDARY_SHA256:
        raise ValueError("Installed Geo boundary resource failed integrity validation")
    value = json.loads(raw)
    return {
        code: tuple(
            (
                ring,
                (
                    min(p[0] for p in ring),
                    min(p[1] for p in ring),
                    max(p[0] for p in ring),
                    max(p[1] for p in ring),
                ),
            )
            for ring in rings
        )
        for code, rings in value["rings"].items()
    }


def _inside(rings, x, y):
    inside = False
    for ring, (left, bottom, right, top) in rings:
        if not (left <= x <= right and bottom <= y <= top):
            continue
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                inside = not inside
    return inside


def _near_boundary(rings, x, y):
    # Local tangent-plane distance is sufficient for a conservative 500 m guard;
    # all tested segments are near the point, away from poles/antimeridian.
    mx, my = 111_320 * cos(radians(y)), 111_320
    dx, dy = BOUNDARY_GUARD_METERS / max(mx, 1), BOUNDARY_GUARD_METERS / my
    for ring, (left, bottom, right, top) in rings:
        if not (left - dx <= x <= right + dx and bottom - dy <= y <= top + dy):
            continue
        for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
            ax, ay, bx, by = (x1 - x) * mx, (y1 - y) * my, (x2 - x) * mx, (y2 - y) * my
            vx, vy = bx - ax, by - ay
            length = vx * vx + vy * vy
            t = max(0.0, min(1.0, -(ax * vx + ay * vy) / length)) if length else 0.0
            if (ax + t * vx) ** 2 + (ay + t * vy) ** 2 <= BOUNDARY_GUARD_METERS**2:
                return True
    return False


@lru_cache(maxsize=4096)
def service_region(coordinate: GeoCoordinate) -> str:
    if coordinate.datum is MapDatum.GCJ02:
        from mediasense.geo import XYConvertCoordinateConverter

        coordinate = XYConvertCoordinateConverter().convert(coordinate, MapDatum.WGS84)
    rings = _boundaries()
    x, y = coordinate.longitude, coordinate.latitude
    if _near_boundary(rings["CHN"], x, y):
        return "uncertain"
    if any(_inside(rings[c], x, y) for c in ("HKG", "MAC", "TWN")):
        return "overseas"
    return "mainland" if _inside(rings["CHN"], x, y) else "overseas"
