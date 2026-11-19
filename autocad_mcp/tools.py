"""MCP tool catalogue: each tool's name, description, JSON schema and handler.

To add a tool, implement the operation on ``AutoCADClient`` and append a
``ToolSpec`` to ``TOOLS`` - registration and dispatch are automatic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .autocad import AutoCADClient

Args = dict[str, Any]
Handler = Callable[[AutoCADClient, Args], dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    properties: dict[str, Any]
    required: tuple[str, ...]
    handler: Handler

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": self.properties, "required": list(self.required)}


# ---------------------------------------------------------------------- schema helpers

def _point(description: str) -> dict[str, Any]:
    return {"type": "array", "items": {"type": "number"}, "description": description}


def _number(description: str, **extra: Any) -> dict[str, Any]:
    return {"type": "number", "description": description, **extra}


def _string(description: str, **extra: Any) -> dict[str, Any]:
    return {"type": "string", "description": description, **extra}


def _color(description: str = "Color name or ACI number", default: str | None = "white") -> dict[str, Any]:
    return _string(description) if default is None else _string(description, default=default)


def _thickness(description: str) -> dict[str, Any]:
    return _number(description, default=0.0)


COLOR_NAMES = "red, blue, green, yellow, cyan, magenta, white, black, gray, light_gray"
ENTITY_TYPES = "AcDbLine, AcDbCircle, AcDbText, AcDbArc"
NO_ARGS: dict[str, Any] = {}


# ---------------------------------------------------------------------- handlers

def _create_or_get_layer(c: AutoCADClient, a: Args) -> dict[str, Any]:
    success = c.create_or_get_layer(a["layer_name"], a.get("color", "white"), a.get("description", ""))
    return {"success": success, "layer_name": a["layer_name"]}


def _set_current_layer(c: AutoCADClient, a: Args) -> dict[str, Any]:
    return {"success": c.set_current_layer(a["layer_name"]), "layer_name": a["layer_name"]}


# ---------------------------------------------------------------------- catalogue

TOOLS: list[ToolSpec] = [
    # --- Query -------------------------------------------------------------
    ToolSpec(
        "get_drawing_info",
        "Get information about the current AutoCAD drawing including layers",
        NO_ARGS, (),
        lambda c, a: c.get_drawing_info(),
    ),
    ToolSpec(
        "get_entities",
        "Get list of ALL entities in the current drawing with their properties and layer information",
        {"max_entities": {"type": "integer",
                          "description": "Maximum number of entities to retrieve (default: all entities)",
                          "minimum": 1}},
        (),
        lambda c, a: c.get_entities(a.get("max_entities")),
    ),

    # --- Structures & layers ----------------------------------------------
    ToolSpec(
        "create_structure",
        "Create a structured building element (wall, door, window, room) with automatic layer "
        "assignment and labeling",
        {
            "structure_type": _string(
                "Type of structure (wall, door, window, room, furniture, etc.)",
                enum=["wall", "door", "window", "room", "furniture", "electrical", "plumbing", "hvac"],
            ),
            "geometry_data": {
                "type": "object",
                "description": "Geometry data - use start/end for lines, center/radius for circles, "
                               "corner1/corner2 for rectangles",
            },
            "color": _color("Color name (uses layer default if not specified)", default=None),
            "thickness": _thickness("Structure thickness (0.1 default for walls)"),
            "custom_layer": _string("Custom layer name (uses automatic layer if not specified)"),
            "label": _string("Optional text label for the structure"),
        },
        ("structure_type", "geometry_data"),
        lambda c, a: c.create_structure(
            a["structure_type"], a["geometry_data"], a.get("color"),
            a.get("thickness", 0.0), a.get("custom_layer"), a.get("label"),
        ),
    ),
    ToolSpec(
        "create_or_get_layer",
        "Create a new layer or get existing layer with specified properties",
        {
            "layer_name": _string("Name of the layer"),
            "color": _color("Layer color"),
            "description": _string("Layer description", default=""),
        },
        ("layer_name",),
        _create_or_get_layer,
    ),
    ToolSpec(
        "set_current_layer",
        "Set the current active layer",
        {"layer_name": _string("Name of the layer to make active")},
        ("layer_name",),
        _set_current_layer,
    ),

    # --- Drawing primitives -----------------------------------------------
    ToolSpec(
        "create_line",
        "Create a line in AutoCAD with optional color and thickness",
        {
            "start": _point("Start point [x, y] or [x, y, z]"),
            "end": _point("End point [x, y] or [x, y, z]"),
            "color": _color(f"Color name ({COLOR_NAMES}) or ACI number"),
            "thickness": _thickness("Line thickness (creates parallel lines)"),
        },
        ("start", "end"),
        lambda c, a: c.create_line(a["start"], a["end"], a.get("color", "white"), a.get("thickness", 0.0)),
    ),
    ToolSpec(
        "create_circle",
        "Create a circle in AutoCAD with optional color and thickness",
        {
            "center": _point("Center point [x, y] or [x, y, z]"),
            "radius": _number("Circle radius"),
            "color": _color(),
            "thickness": _thickness("Circle thickness (creates concentric circles)"),
        },
        ("center", "radius"),
        lambda c, a: c.create_circle(a["center"], a["radius"], a.get("color", "white"), a.get("thickness", 0.0)),
    ),
    ToolSpec(
        "create_rectangle",
        "Create a rectangle in AutoCAD with optional color and thickness",
        {
            "corner1": _point("First corner [x, y]"),
            "corner2": _point("Opposite corner [x, y]"),
            "color": _color(),
            "thickness": _thickness("Rectangle thickness"),
        },
        ("corner1", "corner2"),
        lambda c, a: c.create_rectangle(a["corner1"], a["corner2"], a.get("color", "white"),
                                        a.get("thickness", 0.0)),
    ),
    ToolSpec(
        "create_text",
        "Create text in AutoCAD with optional color",
        {
            "position": _point("Text position [x, y] or [x, y, z]"),
            "text": _string("Text content"),
            "height": _number("Text height", default=1.0),
            "color": _color("Text color name or ACI number"),
        },
        ("position", "text"),
        lambda c, a: c.create_text(a["position"], a["text"], a.get("height", 1.0), a.get("color", "white")),
    ),
    ToolSpec(
        "create_arc",
        "Create an arc in AutoCAD with optional color and thickness",
        {
            "center": _point("Center point [x, y] or [x, y, z]"),
            "radius": _number("Arc radius"),
            "start_angle": _number("Start angle in degrees (0° = positive X axis)"),
            "end_angle": _number("End angle in degrees"),
            "color": _color(),
            "thickness": _thickness("Arc thickness (creates parallel arcs with connecting lines)"),
        },
        ("center", "radius", "start_angle", "end_angle"),
        lambda c, a: c.create_arc(a["center"], a["radius"], a["start_angle"], a["end_angle"],
                                  a.get("color", "white"), a.get("thickness", 0.0)),
    ),

    # --- Deletion -----------------------------------------------------------
    ToolSpec(
        "delete_entity_by_handle",
        "Delete a specific entity by its handle (get handle from get_entities)",
        {"handle": _string("Entity handle to delete")},
        ("handle",),
        lambda c, a: c.delete_entity_by_handle(a["handle"]),
    ),
    ToolSpec(
        "delete_entities_by_handles",
        "Delete multiple entities by their handles",
        {"handles": {"type": "array", "items": {"type": "string"},
                     "description": "List of entity handles to delete"}},
        ("handles",),
        lambda c, a: c.delete_entities_by_handles(a["handles"]),
    ),
    ToolSpec(
        "delete_entities_by_type",
        "Delete all entities of a specific type (e.g., 'AcDbLine', 'AcDbCircle', 'AcDbText', 'AcDbArc')",
        {"entity_type": _string(f"AutoCAD entity type (e.g., {ENTITY_TYPES})")},
        ("entity_type",),
        lambda c, a: c.delete_entities_by_type(a["entity_type"]),
    ),
    ToolSpec(
        "delete_entities_by_layer",
        "Delete all entities on a specific layer",
        {"layer_name": _string("Layer name (e.g., '0' for default layer, 'WALLS', 'DOORS', etc.)")},
        ("layer_name",),
        lambda c, a: c.delete_entities_by_layer(a["layer_name"]),
    ),
    ToolSpec(
        "delete_entities_by_color",
        "Delete all entities with a specific color",
        {"color": _color("Color name (red, blue, green, etc.) or ACI number", default=None)},
        ("color",),
        lambda c, a: c.delete_entities_by_color(a["color"]),
    ),
    ToolSpec(
        "delete_entities_by_type_and_color",
        "Delete entities of a specific type AND color (e.g., only green text, only red lines)",
        {
            "entity_type": _string("AutoCAD entity type (e.g., AcDbText, AcDbLine, AcDbCircle, AcDbArc)"),
            "color": _color("Color name (red, blue, green, etc.) or ACI number", default=None),
        },
        ("entity_type", "color"),
        lambda c, a: c.delete_entities_by_type_and_color(a["entity_type"], a["color"]),
    ),
    ToolSpec(
        "delete_last_entities",
        "Delete the last N entities created (most recent entities)",
        {"count": {"type": "integer", "description": "Number of recent entities to delete",
                   "default": 1, "minimum": 1}},
        (),
        lambda c, a: c.delete_last_entities(a.get("count", 1)),
    ),
    ToolSpec(
        "delete_all_entities",
        "Delete ALL entities in the drawing (requires confirmation)",
        {"confirm": {"type": "boolean",
                     "description": "Must be set to true to confirm deletion of all entities",
                     "default": False}},
        ("confirm",),
        lambda c, a: c.delete_all_entities(a.get("confirm", False)),
    ),

    # --- Editing & view -------------------------------------------------------
    ToolSpec(
        "undo_last_operation",
        "Undo the last operation in AutoCAD (equivalent to Ctrl+Z)",
        NO_ARGS, (),
        lambda c, a: c.undo_last_operation(),
    ),
    ToolSpec(
        "change_entity_color",
        "Change the color of an existing entity by its handle",
        {
            "handle": _string("Entity handle (get from get_entities)"),
            "color": _color("New color name or ACI number", default=None),
        },
        ("handle", "color"),
        lambda c, a: c.change_entity_color(a["handle"], a["color"]),
    ),
    ToolSpec(
        "zoom_extents",
        "Zoom to show all objects in the drawing",
        NO_ARGS, (),
        lambda c, a: c.zoom_extents(),
    ),
]

TOOLS_BY_NAME: dict[str, ToolSpec] = {tool.name: tool for tool in TOOLS}
