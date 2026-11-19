"""Static configuration: server identity, AutoCAD constants, colours and layer standards."""

from __future__ import annotations

SERVER_NAME = "autocad-com-mcp"
SERVER_VERSION = "1.0.0"
AC_ACTIVE_VIEWPORT = 0  

# --- Timing -----------------------------------------------------------------
# AutoCAD's COM interface drops calls when hammered; these pauses were tuned
# empirically and are what makes entity creation reliable.
OPERATION_DELAY = 1.0          # seconds after every entity-creating COM call
DELETE_DELAY = 0.2             # seconds after a single-entity delete
UNDO_DELAY = 0.5               # seconds for AutoCAD to process the U command
CONNECT_DELAY = 2.0            # seconds for a freshly launched AutoCAD to start
BULK_DELETE_PAUSE_EVERY = 25   # pause briefly after this many bulk deletes
BULK_DELETE_PAUSE = 0.1
ENTITY_READ_PAUSE_EVERY = 500  # pause briefly after reading this many entities
ENTITY_READ_PAUSE = 0.1

# --- Geometry defaults --------------------------------------------------------
DEFAULT_WALL_THICKNESS = 0.1
WINDOW_SILL_OFFSET = 0.05      # distance of the inner window line from the opening
MIN_INNER_RADIUS = 0.1         # smallest inner radius when thickening circles/arcs
LABEL_TEXT_HEIGHT = 0.2

# --- Colours ------------------------------------------------------------------
DEFAULT_COLOR_INDEX = 7  # white

# AutoCAD Color Index (ACI) values by name.
COLOR_MAP: dict[str, int] = {
    "red": 1,
    "yellow": 2,
    "green": 3,
    "cyan": 4,
    "blue": 5,
    "magenta": 6,
    "white": 7,
    "gray": 8,
    "light_gray": 9,
    "black": 0,
    "bylayer": 256,
    "byblock": 0,
}

# --- Layers -------------------------------------------------------------------
DEFAULT_LAYER = "0"
ANNOTATION_LAYER = "ANNOTATION"

# Standard layers created on connect, keyed by layer type.
LAYER_DEFINITIONS: dict[str, dict[str, str]] = {
    "walls": {"name": "WALLS", "color": "white", "description": "Building walls and partitions"},
    "doors": {"name": "DOORS", "color": "green", "description": "Door openings and frames"},
    "windows": {"name": "WINDOWS", "color": "cyan", "description": "Window openings and frames"},
    "furniture": {"name": "FURNITURE", "color": "yellow", "description": "Furniture and fixtures"},
    "electrical": {"name": "ELECTRICAL", "color": "red", "description": "Electrical fixtures and outlets"},
    "plumbing": {"name": "PLUMBING", "color": "blue", "description": "Plumbing fixtures and pipes"},
    "hvac": {"name": "HVAC", "color": "magenta", "description": "HVAC ducts and equipment"},
    "structure": {"name": "STRUCTURE", "color": "gray", "description": "Structural elements"},
    "annotation": {"name": ANNOTATION_LAYER, "color": "white", "description": "Text and dimensions"},
    "site": {"name": "SITE", "color": "green", "description": "Site elements and landscaping"},
    "utilities": {"name": "UTILITIES", "color": "red", "description": "Utility lines and equipment"},
}

# Keyword -> layer type. A structure type is matched by substring, and the
# first keyword found wins, so dict order matters.
STRUCTURE_KEYWORDS: dict[str, str] = {
    "wall": "walls",
    "door": "doors",
    "window": "windows",
    "furniture": "furniture",
    "chair": "furniture",
    "table": "furniture",
    "bed": "furniture",
    "electrical": "electrical",
    "outlet": "electrical",
    "switch": "electrical",
    "light": "electrical",
    "plumbing": "plumbing",
    "toilet": "plumbing",
    "sink": "plumbing",
    "hvac": "hvac",
    "vent": "hvac",
    "duct": "hvac",
    "structure": "structure",
    "beam": "structure",
    "column": "structure",
    "text": "annotation",
    "dimension": "annotation",
    "site": "site",
    "tree": "site",
    "utility": "utilities",
}
