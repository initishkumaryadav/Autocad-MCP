"""Primitive drawing operations: lines, circles, rectangles, text and arcs.

"Thickness" is drawn as outline geometry (parallel lines with end caps,
concentric circles, parallel arcs), not as AutoCAD lineweight.
"""

from __future__ import annotations

import math
from typing import Sequence

from .. import config
from ..com import to_variant_point, variant_point
from ..geometry import offset_segment, rectangle_edges
from .base import AutoCADBase, Color, Result, autocad_operation

Point = Sequence[float]


def _with_thickness(text: str, thickness: float) -> str:
    return text + (f" and thickness {thickness}" if thickness > 0 else "")


def _type_name(base: str, thickness: float) -> str:
    return base + (" with thickness" if thickness > 0 else "")


class DrawingMixin(AutoCADBase):

    def _add_line_2d(self, a: Point, b: Point, color: Color) -> str | None:
        """Add a line in the z=0 plane (used for thickness outlines)."""
        return self.add_to_model_space(
            lambda ms: ms.AddLine(variant_point(a[0], a[1]), variant_point(b[0], b[1])), color
        )

    @autocad_operation("create line")
    def create_line(self, start: Point, end: Point, color: Color = "white", thickness: float = 0.0) -> Result:
        """Create a line; with thickness > 0 it becomes a closed outline of that width."""
        main = self.add_to_model_space(
            lambda ms: ms.AddLine(to_variant_point(start), to_variant_point(end)), color
        )
        handles = [main or "line_created"]

        if thickness > 0 and main:
            parallel = offset_segment(start, end, thickness / 2.0)
            if parallel:
                start_p, end_p = parallel
                # Parallel edge, then the two end caps.
                for a, b in ((start_p, end_p), (start, start_p), (end, end_p)):
                    handle = self._add_line_2d(a, b, color)
                    if handle:
                        handles.append(handle)

        return {
            "success": True,
            "handles": handles,
            "type": _type_name("AcDbLine", thickness),
            "color": color,
            "thickness": thickness,
            "message": _with_thickness(f"Line created from {start} to {end} with color {color}", thickness),
        }

    @autocad_operation("create circle")
    def create_circle(self, center: Point, radius: float, color: Color = "white", thickness: float = 0.0) -> Result:
        """Create a circle; with thickness > 0 adds concentric outer and inner circles."""
        radii = [float(radius)]
        if thickness > 0:
            radii.append(radius + thickness / 2)
            radii.append(max(config.MIN_INNER_RADIUS, radius - thickness / 2))

        handles = []
        for r in radii:
            handle = self.add_to_model_space(lambda ms, r=r: ms.AddCircle(to_variant_point(center), float(r)), color)
            if handle:
                handles.append(handle)

        return {
            "success": True,
            "handles": handles,
            "type": _type_name("AcDbCircle", thickness),
            "color": color,
            "thickness": thickness,
            "message": _with_thickness(
                f"Circle created at {center} with radius {radius}, color {color}", thickness
            ),
        }

    @autocad_operation("create rectangle")
    def create_rectangle(self, corner1: Point, corner2: Point, color: Color = "white",
                         thickness: float = 0.0) -> Result:
        """Create an axis-aligned rectangle from four lines."""
        edges = rectangle_edges(corner1, corner2)

        handles = []
        for start, end in edges:
            result = self.create_line(start, end, color, thickness)
            if result.get("success"):
                handles.extend(result.get("handles", []))

        (x1, y1), (x2, y2) = edges[0][0], edges[2][0]
        return {
            "success": True,
            "handles": handles,
            "type": _type_name("Rectangle", thickness),
            "color": color,
            "thickness": thickness,
            "message": _with_thickness(
                f"Rectangle created from ({x1},{y1}) to ({x2},{y2}) with color {color}", thickness
            ),
        }

    @autocad_operation("create text")
    def create_text(self, position: Point, text: str, height: float = 1.0, color: Color = "white") -> Result:
        """Create a single-line text entity."""
        handle = self.add_to_model_space(
            lambda ms: ms.AddText(str(text), to_variant_point(position), float(height)), color
        )
        return {
            "success": True,
            "handle": handle or "text_created",
            "type": "AcDbText",
            "color": color,
            "message": f"Text '{text}' created at {position} with height {height} and color {color}",
        }

    @autocad_operation("create arc")
    def create_arc(self, center: Point, radius: float, start_angle: float, end_angle: float,
                   color: Color = "white", thickness: float = 0.0) -> Result:
        """Create an arc (angles in degrees, counter-clockwise from +X).

        With thickness > 0 adds parallel inner and outer arcs.
        """
        start_rad = math.radians(start_angle)
        end_rad = math.radians(end_angle)

        def add_arc(r: float) -> str | None:
            return self.add_to_model_space(
                lambda ms: ms.AddArc(to_variant_point(center), float(r), start_rad, end_rad), color
            )

        handles = [add_arc(radius) or "arc_main"]
        if thickness > 0:
            for r in (max(config.MIN_INNER_RADIUS, radius - thickness / 2), radius + thickness / 2):
                handle = add_arc(r)
                if handle:
                    handles.append(handle)

        return {
            "success": True,
            "handles": handles,
            "type": _type_name("AcDbArc", thickness),
            "color": color,
            "thickness": thickness,
            "start_angle": start_angle,
            "end_angle": end_angle,
            "message": _with_thickness(
                f"Arc created at {center} with radius {radius}, from {start_angle}° to {end_angle}°, color {color}",
                thickness,
            ),
        }
