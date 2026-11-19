"""Building elements (walls, doors, windows, rooms) placed on standard layers."""

from __future__ import annotations

from typing import Any, Callable, Optional

from .. import config
from ..geometry import midpoint, offset_segment
from .base import Color, Result, autocad_operation
from .drawing import DrawingMixin
from .layers import LayerMixin

Geometry = dict[str, Any]


def _missing(geometry_data: Geometry, *keys: str) -> bool:
    return any(key not in geometry_data for key in keys)


class StructureMixin(LayerMixin, DrawingMixin):

    def _structure_builder(self, structure_type: str) -> Optional[Callable[[Geometry, Color, float], Result]]:
        """The dedicated builder for a structure type, or None for generic geometry."""
        builders = {
            "wall": self.create_wall,
            "partition": self.create_wall,
            "door": self.create_door,
            "opening": self.create_door,
            "window": self.create_window,
            "room": self.create_room,
        }
        return builders.get(structure_type.lower())

    def _create_generic(self, geometry_data: Geometry, color: Color, thickness: float) -> Result:
        """Draw a line, circle or rectangle depending on which keys are present."""
        if not _missing(geometry_data, "start", "end"):
            return self.create_line(geometry_data["start"], geometry_data["end"], color, thickness)
        if not _missing(geometry_data, "center", "radius"):
            return self.create_circle(geometry_data["center"], geometry_data["radius"], color, thickness)
        if not _missing(geometry_data, "corner1", "corner2"):
            return self.create_rectangle(geometry_data["corner1"], geometry_data["corner2"], color, thickness)
        return {"error": "Unsupported geometry data: provide start/end, center/radius or corner1/corner2"}

    @autocad_operation("create structure")
    def create_structure(self, structure_type: str, geometry_data: Geometry,
                         color: Color = None, thickness: float = 0.0,
                         custom_layer: Optional[str] = None, label: Optional[str] = None) -> Result:
        """Create a structure on its standard layer (or ``custom_layer``), optionally labelled."""
        if custom_layer:
            layer_name = custom_layer
            self.create_or_get_layer(layer_name, color or "white", f"Custom layer for {structure_type}")
        else:
            layer_name = self.get_layer_for_structure_type(structure_type)

        if color is None:
            color = self.default_color_for_layer(layer_name) or "bylayer"

        builder = self._structure_builder(structure_type) or self._create_generic

        with self.active_layer(layer_name):
            result = builder(geometry_data, color, thickness)
            if "error" in result:
                return {"error": f"{structure_type}: {result['error']}"}

            handles = list(result.get("handles", []))
            if label:
                label_result = self.add_structure_label(geometry_data, label, layer_name)
                if label_result.get("success"):
                    handles.append(label_result["handle"])

        message = f"{structure_type} created on layer {layer_name}"
        if label:
            message += f" with label '{label}'"
        return {
            "success": True,
            "structure_type": structure_type,
            "layer": layer_name,
            "handles": handles,
            "color": color,
            "thickness": thickness,
            "label": label,
            "message": message,
        }

    def create_wall(self, geometry_data: Geometry, color: Color = "white",
                    thickness: float = config.DEFAULT_WALL_THICKNESS) -> Result:
        """A wall is a thick line; it always gets at least the default wall thickness."""
        if _missing(geometry_data, "start", "end"):
            return {"error": "Wall requires start and end points"}
        wall_thickness = thickness if thickness > 0 else config.DEFAULT_WALL_THICKNESS
        return self.create_line(geometry_data["start"], geometry_data["end"], color, wall_thickness)

    def create_door(self, geometry_data: Geometry, color: Color = "green", thickness: float = 0.0) -> Result:
        """A door opening line, plus a quarter-circle swing when ``width`` is given."""
        if _missing(geometry_data, "start", "end"):
            return {"error": "Door requires start and end points"}

        start, end = geometry_data["start"], geometry_data["end"]
        handles = list(self.create_line(start, end, color, thickness).get("handles", []))

        if "width" in geometry_data:
            swing = self.create_arc(start, geometry_data["width"], 0, 90, color, 0)
            handles.extend(swing.get("handles", []))

        return {
            "success": True,
            "handles": handles,
            "type": "Door",
            "color": color,
            "message": f"Door created from {start} to {end}",
        }

    def create_window(self, geometry_data: Geometry, color: Color = "cyan", thickness: float = 0.0) -> Result:
        """A window opening line plus a parallel inner line marking the glazing."""
        if _missing(geometry_data, "start", "end"):
            return {"error": "Window requires start and end points"}

        start, end = geometry_data["start"], geometry_data["end"]
        handles = list(self.create_line(start, end, color, thickness).get("handles", []))

        inner = offset_segment(start, end, config.WINDOW_SILL_OFFSET)
        if inner:
            handles.extend(self.create_line(inner[0], inner[1], color, 0).get("handles", []))

        return {
            "success": True,
            "handles": handles,
            "type": "Window",
            "color": color,
            "message": f"Window created from {start} to {end}",
        }

    def create_room(self, geometry_data: Geometry, color: Color = "white",
                    thickness: float = config.DEFAULT_WALL_THICKNESS) -> Result:
        """A room is a rectangle whose edges are drawn with the given wall thickness."""
        if _missing(geometry_data, "corner1", "corner2"):
            return {"error": "Room requires corner1 and corner2 points"}
        return self.create_rectangle(geometry_data["corner1"], geometry_data["corner2"], color, thickness)

    @autocad_operation("add label")
    def add_structure_label(self, geometry_data: Geometry, label: str, layer_name: str) -> Result:
        """Place a text label at the centre of the structure, on the annotation layer."""
        if "center" in geometry_data:
            position = geometry_data["center"]
        elif not _missing(geometry_data, "start", "end"):
            position = midpoint(geometry_data["start"], geometry_data["end"])
        elif not _missing(geometry_data, "corner1", "corner2"):
            position = midpoint(geometry_data["corner1"], geometry_data["corner2"])
        else:
            position = [0, 0]

        with self.active_layer(config.ANNOTATION_LAYER):
            return self.create_text(position, label, config.LABEL_TEXT_HEIGHT, "white")
