"""Modifying the drawing: deletion, recolouring, undo and view control."""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from .. import config
from ..com import try_get
from .base import Color, Result, autocad_operation
from .query import QueryMixin


class EditingMixin(QueryMixin):

    # ------------------------------------------------------------------ deletion

    def _delete_all_of(self, entities: list[Any]) -> tuple[int, int]:
        """Delete the given entities with periodic pauses. Returns (deleted, failed)."""
        deleted = failed = 0
        for idx, entity in enumerate(entities, start=1):
            try:
                entity.Delete()
                deleted += 1
            except Exception:
                failed += 1
            if idx % config.BULK_DELETE_PAUSE_EVERY == 0:
                time.sleep(config.BULK_DELETE_PAUSE)
        if deleted:
            self.regen()
        return deleted, failed

    @autocad_operation("delete entities")
    def delete_entities_matching(self, predicate: Callable[[Any], bool], description: str) -> Result:
        """Delete every model space entity for which ``predicate`` is true.

        Matches are collected first and deleted afterwards: deleting while
        iterating by index would shift the indices.
        """
        model_space = self.doc.ModelSpace
        to_delete = []
        for i in range(model_space.Count):
            try:
                entity = model_space.Item(i)
                if predicate(entity):
                    to_delete.append(entity)
            except Exception:
                continue

        deleted, failed = self._delete_all_of(to_delete)

        result: Result = {
            "success": True,
            "deleted_count": deleted,
            "message": f"Deleted {deleted} entities ({description})",
        }
        if failed:
            result["failed_count"] = failed
            result["message"] += f", {failed} could not be deleted"
        return result

    @autocad_operation("delete entity")
    def delete_entity_by_handle(self, handle: str) -> Result:
        """Delete a single entity by handle."""
        entity = self.find_entity_by_handle(handle)
        if entity is None:
            return {"error": f"Entity with handle {handle} not found"}

        def delete_operation() -> bool:
            entity.Delete()
            self.regen()
            return True

        if not self.safe_operation(delete_operation, delay=config.DELETE_DELAY):
            return {"error": f"AutoCAD refused to delete entity {handle}"}

        return {
            "success": True,
            "handle": handle,
            "message": f"Entity with handle {handle} deleted successfully",
        }

    @autocad_operation("delete entities")
    def delete_entities_by_handles(self, handles: list[str]) -> Result:
        """Delete several entities by handle, reporting which were missing or failed."""
        deleted: list[str] = []
        not_found: list[str] = []
        failed: list[str] = []

        for handle in handles:
            entity = self.find_entity_by_handle(handle)
            if entity is None:
                not_found.append(handle)
                continue
            try:
                entity.Delete()
                deleted.append(handle)
            except Exception:
                failed.append(handle)

        if deleted:
            self.regen()

        result: Result = {
            "success": True,
            "deleted_count": len(deleted),
            "deleted_handles": deleted,
            "message": f"Deleted {len(deleted)} of {len(handles)} entities",
        }
        if not_found:
            result["not_found"] = not_found
        if failed:
            result["failed"] = failed
        return result

    def delete_entities_by_type(self, entity_type: str) -> Result:
        """Delete all entities of an ObjectName type, e.g. AcDbLine (case-insensitive)."""
        target = entity_type.lower()
        return self.delete_entities_matching(
            lambda e: str(e.ObjectName).lower() == target, f"type: {entity_type}"
        )

    def delete_entities_by_layer(self, layer_name: str) -> Result:
        """Delete all entities on a layer (case-insensitive)."""
        target = layer_name.upper()
        return self.delete_entities_matching(
            lambda e: str(e.Layer).upper() == target, f"layer: {layer_name}"
        )

    def delete_entities_by_color(self, color: Color) -> Result:
        """Delete all entities whose own colour matches (ByLayer entities are 256)."""
        color_index = self.get_color_index(color)
        return self.delete_entities_matching(
            lambda e: int(e.Color) == color_index, f"color: {color}"
        )

    def delete_entities_by_type_and_color(self, entity_type: str, color: Color) -> Result:
        """Delete entities matching both a type and a colour."""
        target_type = entity_type.lower()
        color_index = self.get_color_index(color)
        return self.delete_entities_matching(
            lambda e: str(e.ObjectName).lower() == target_type and int(e.Color) == color_index,
            f"type: {entity_type}, color: {color}",
        )

    @autocad_operation("delete last entities")
    def delete_last_entities(self, count: int = 1) -> Result:
        """Delete the ``count`` most recently added model space entities."""
        model_space = self.doc.ModelSpace
        total = int(model_space.Count)
        if total == 0:
            return {"success": True, "deleted_count": 0, "message": "Drawing is empty, nothing to delete"}

        count = min(count, total)
        to_delete = []
        for i in range(total - count, total):
            try:
                to_delete.append(model_space.Item(i))
            except Exception:
                continue

        deleted, _ = self._delete_all_of(to_delete)
        return {
            "success": True,
            "deleted_count": deleted,
            "message": f"Deleted the last {deleted} entities",
        }

    def delete_all_entities(self, confirm: bool = False) -> Result:
        """Delete every entity in model space. Requires ``confirm=True``."""
        if not confirm:
            return {"error": "Deletion of all entities requires confirm=true"}
        return self.delete_entities_matching(lambda e: True, "all entities")

    # ------------------------------------------------------------------ other edits

    @autocad_operation("change entity color")
    def change_entity_color(self, handle: str, color: Color) -> Result:
        """Recolour an existing entity."""
        entity = self.find_entity_by_handle(handle)
        if entity is None:
            return {"error": f"Entity with handle {handle} not found"}

        color_index = self.get_color_index(color)
        entity.Color = color_index
        self.regen()

        return {
            "success": True,
            "handle": handle,
            "color": color,
            "color_index": color_index,
            "message": f"Entity {handle} color changed to {color}",
        }

    @autocad_operation("undo")
    def undo_last_operation(self) -> Result:
        """Send AutoCAD's U command (one undo step, like Ctrl+Z)."""
        def entity_count() -> Optional[int]:
            return try_get(lambda: int(self.doc.ModelSpace.Count), None)

        before_count = entity_count()

        self.doc.SendCommand("_U\n")
        time.sleep(config.UNDO_DELAY)
        self.regen()

        result: Result = {"success": True, "message": "Undo command sent to AutoCAD"}
        after_count = entity_count()
        if after_count is None:
            return result

        result["entity_count_before"] = before_count
        result["entity_count_after"] = after_count
        # AutoCAD groups COM operations in its undo stack, so one undo may revert
        # only part of a multi-step creation (e.g. just the colour change).
        if before_count is not None and after_count == before_count:
            result["note"] = ("Entity count unchanged - the undone step may have been "
                              "a property change or partial operation; call again to undo further")
        return result

    @autocad_operation("zoom extents")
    def zoom_extents(self) -> Result:
        """Zoom the view to fit every object."""
        self.acad_app.ZoomExtents()
        return {"success": True, "message": "Zoom extents executed"}
