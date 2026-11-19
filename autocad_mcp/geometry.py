"""Pure 2D geometry helpers (no AutoCAD dependency, safe to unit test)."""

from __future__ import annotations

import math
from typing import Optional, Sequence

Point = Sequence[float]


def offset_segment(start: Point, end: Point, distance: float) -> Optional[tuple[list[float], list[float]]]:
    """Return the segment start->end shifted ``distance`` to its left (2D).

    Returns None for a zero-length segment, which has no defined normal.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return None

    nx = -dy / length * distance
    ny = dx / length * distance
    return [start[0] + nx, start[1] + ny], [end[0] + nx, end[1] + ny]


def midpoint(a: Point, b: Point) -> list[float]:
    """2D midpoint of two points."""
    return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]


def rectangle_edges(corner1: Point, corner2: Point) -> list[tuple[list[float], list[float]]]:
    """The four edges (bottom, right, top, left) of an axis-aligned rectangle."""
    x1, y1 = float(corner1[0]), float(corner1[1])
    x2, y2 = float(corner2[0]), float(corner2[1])
    return [
        ([x1, y1], [x2, y1]),  # bottom
        ([x2, y1], [x2, y2]),  # right
        ([x2, y2], [x1, y2]),  # top
        ([x1, y2], [x1, y1]),  # left
    ]
