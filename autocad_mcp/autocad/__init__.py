"""AutoCAD automation over COM, independent of MCP.

``AutoCADClient`` combines the operation mixins into one object:

    base.py        connection, colour lookup, COM helpers
    layers.py      layer creation / activation, structure-type -> layer mapping
    drawing.py     lines, circles, rectangles, text, arcs
    structures.py  walls, doors, windows, rooms, labels
    query.py       drawing info, entity listing, handle lookup
    editing.py     deletion, recolouring, undo, zoom
"""

from .base import AutoCADBase, autocad_operation
from .editing import EditingMixin
from .structures import StructureMixin


class AutoCADClient(StructureMixin, EditingMixin):
    """Every AutoCAD operation exposed by this package."""


__all__ = ["AutoCADBase", "AutoCADClient", "autocad_operation"]
