"""Layer creation, activation and the structure-type -> layer mapping."""

from __future__ import annotations

import contextlib
import logging
from typing import Iterator, Optional

from .. import config
from .base import AutoCADBase

log = logging.getLogger(__name__)


class LayerMixin(AutoCADBase):

    def _on_connected(self) -> None:
        super()._on_connected()
        self.ensure_structure_layers()

    def create_or_get_layer(self, layer_name: str, color: str = "white", description: str = "") -> bool:
        """Create a layer if it does not exist yet. Returns True if the layer exists afterwards."""
        if not self.ensure_connection():
            return False

        try:
            layers = self.doc.Layers
            try:
                layers.Item(layer_name)
                return True  # already exists
            except Exception:
                pass

            new_layer = layers.Add(layer_name)
            new_layer.Color = self.get_color_index(color)
            try:
                new_layer.Description = description
            except Exception:
                pass  # Description is not available in all AutoCAD versions
            return True
        except Exception:
            log.debug("Could not create layer %s", layer_name, exc_info=True)
            return False

    def set_current_layer(self, layer_name: str) -> bool:
        """Make ``layer_name`` the active layer. Returns True on success."""
        if not self.ensure_connection():
            return False

        try:
            self.doc.ActiveLayer = self.doc.Layers.Item(layer_name)
            return True
        except Exception:
            log.debug("Could not activate layer %s", layer_name, exc_info=True)
            return False

    def ensure_structure_layers(self) -> None:
        """Create every predefined structure layer that is missing."""
        for layer_info in self.layer_definitions.values():
            self.create_or_get_layer(layer_info["name"], layer_info["color"], layer_info["description"])

    def get_layer_for_structure_type(self, structure_type: str) -> str:
        """Pick the standard layer for a structure type, or layer "0" if none matches."""
        structure_type_lower = structure_type.lower()
        for keyword, layer_type in config.STRUCTURE_KEYWORDS.items():
            if keyword in structure_type_lower:
                return self.layer_definitions[layer_type]["name"]
        return config.DEFAULT_LAYER

    def default_color_for_layer(self, layer_name: str) -> Optional[str]:
        """The colour of a predefined layer, or None for layers we did not define."""
        for layer_info in self.layer_definitions.values():
            if layer_info["name"] == layer_name:
                return layer_info["color"]
        return None

    @contextlib.contextmanager
    def active_layer(self, layer_name: str) -> Iterator[None]:
        """Temporarily switch the active layer, restoring the previous one afterwards."""
        original: Optional[str] = None
        try:
            original = str(self.doc.ActiveLayer.Name)
            self.set_current_layer(layer_name)
        except Exception:
            log.debug("Could not switch to layer %s", layer_name, exc_info=True)

        try:
            yield
        finally:
            if original:
                self.set_current_layer(original)
