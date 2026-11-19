"""Read-only queries: drawing info, entity listing, handle lookup."""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .. import config
from ..com import try_get
from .base import AutoCADBase, Result, autocad_operation

log = logging.getLogger(__name__)


def _xyz(point: Any) -> list[float]:
    return [point[0], point[1], point[2]]


def describe_entity(entity: Any, index: int) -> dict[str, Any]:
    """Serialisable summary of a model space entity, with geometry for common types."""
    info: dict[str, Any] = {
        "index": index,
        "type": str(entity.ObjectName),
        "layer": str(entity.Layer),
        "handle": str(entity.Handle),
        "color": int(entity.Color),
    }

    try:
        info["visible"] = bool(entity.Visible)
    except Exception:
        pass

    try:
        object_name = info["type"]
        if object_name == "AcDbLine":
            info["start_point"] = _xyz(entity.StartPoint)
            info["end_point"] = _xyz(entity.EndPoint)
        elif object_name == "AcDbCircle":
            info["center"] = _xyz(entity.Center)
            info["radius"] = float(entity.Radius)
        elif object_name == "AcDbText":
            info["position"] = _xyz(entity.InsertionPoint)
            info["text_string"] = str(entity.TextString)
            info["height"] = float(entity.Height)
    except Exception:
        pass  # geometry is a best-effort extra

    return info


def describe_layer(layer: Any) -> dict[str, Any]:
    return {
        "name": str(layer.Name),
        "color": int(layer.Color),
        "frozen": bool(layer.Freeze),
        "locked": bool(layer.Lock),
    }


class QueryMixin(AutoCADBase):

    @autocad_operation("get drawing info")
    def get_drawing_info(self) -> Result:
        """File name, path, save state, active layer, entity count and all layers."""
        doc = self.doc
        info: Result = {
            "filename": try_get(lambda: str(doc.Name), "Unknown"),
            "path": try_get(lambda: str(doc.Path) if doc.Path else "Not saved", "Unknown"),
            "entity_count": try_get(lambda: int(doc.ModelSpace.Count), 0),
            "saved": try_get(lambda: bool(doc.Saved), False),
            "current_layer": try_get(lambda: str(doc.ActiveLayer.Name), "Unknown"),
            "total_layers": 0,
            "available_layers": [],
        }

        try:
            layers = doc.Layers
            info["total_layers"] = int(layers.Count)
            for i in range(layers.Count):
                try:
                    info["available_layers"].append(describe_layer(layers.Item(i)))
                except Exception:
                    continue
        except Exception:
            log.debug("Could not read layers", exc_info=True)

        return info

    @autocad_operation("get entities")
    def get_entities(self, max_entities: Optional[int] = None) -> Result:
        """All model space entities (or the first ``max_entities``), also grouped by layer."""
        model_space = self.doc.ModelSpace
        total_count = try_get(lambda: int(model_space.Count), 0)
        count = total_count if max_entities is None else min(total_count, max_entities)

        entities = []
        for i in range(count):
            try:
                entities.append(describe_entity(model_space.Item(i), i))
            except Exception:
                continue  # skip unreadable entities
            # Give COM a breather on very large drawings.
            if (i + 1) % config.ENTITY_READ_PAUSE_EVERY == 0 and i + 1 < count:
                time.sleep(config.ENTITY_READ_PAUSE)

        entities_by_layer: dict[str, list[dict[str, Any]]] = {}
        for entity in entities:
            entities_by_layer.setdefault(entity["layer"], []).append(entity)

        return {
            "entities": entities,
            "entities_by_layer": entities_by_layer,
            "total_count": total_count,
            "returned_count": len(entities),
            "layer_summary": {layer: len(ents) for layer, ents in entities_by_layer.items()},
        }

    def find_entity_by_handle(self, handle: str) -> Any:
        """Look up an entity by handle; falls back to scanning model space. None if absent."""
        try:
            return self.doc.HandleToObject(handle)
        except Exception:
            pass

        try:
            model_space = self.doc.ModelSpace
            for i in range(model_space.Count):
                try:
                    obj = model_space.Item(i)
                    if str(obj.Handle) == handle:
                        return obj
                except Exception:
                    continue
        except Exception:
            log.debug("Handle scan failed", exc_info=True)
        return None
