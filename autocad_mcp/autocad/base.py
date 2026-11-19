"""Connection management and helpers shared by every AutoCAD operation mixin."""

from __future__ import annotations

import copy
import functools
import logging
import time
from typing import Any, Callable, Optional, TypeVar, Union

import win32com.client

from .. import config
from ..com import call_with_delay, handle_of

log = logging.getLogger(__name__)

Result = dict[str, Any]
Color = Union[str, int, None]
F = TypeVar("F", bound=Callable[..., Result])

NOT_CONNECTED: Result = {"error": "Not connected to AutoCAD"}


def autocad_operation(action: str) -> Callable[[F], F]:
    """Decorator for public operations that return a result dict.

    Makes sure AutoCAD is connected before the call, and turns any exception
    into ``{"error": "Failed to <action>: <reason>"}``.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(self: "AutoCADBase", *args: Any, **kwargs: Any) -> Result:
            if not self.ensure_connection():
                return dict(NOT_CONNECTED)
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                log.debug("Failed to %s", action, exc_info=True)
                return {"error": f"Failed to {action}: {e}"}

        return wrapper  # type: ignore[return-value]

    return decorator


class AutoCADBase:
    """Holds the COM connection to AutoCAD and the low-level helpers."""

    def __init__(self) -> None:
        self.acad_app: Any = None
        self.doc: Any = None
        self.connected = False

        # Per-instance copies so callers can customise without touching the defaults.
        self.color_map: dict[str, int] = dict(config.COLOR_MAP)
        self.layer_definitions: dict[str, dict[str, str]] = copy.deepcopy(config.LAYER_DEFINITIONS)

    # ------------------------------------------------------------------ connection

    def connect_to_autocad(self) -> bool:
        """Attach to a running AutoCAD, or launch one with a new drawing."""
        try:
            self.acad_app = win32com.client.GetActiveObject("AutoCAD.Application")
            self.acad_app.Visible = True
            self.doc = self.acad_app.ActiveDocument
            if not self.doc:
                return False
            _ = str(self.doc.Name)  # verify the document actually responds
        except Exception:
            log.debug("No running AutoCAD instance; launching a new one", exc_info=True)
            try:
                self.acad_app = win32com.client.Dispatch("AutoCAD.Application")
                self.acad_app.Visible = True
                time.sleep(config.CONNECT_DELAY)
                self.doc = self.acad_app.Documents.Add()
            except Exception:
                log.warning("Could not connect to or launch AutoCAD", exc_info=True)
                return False

        self.connected = True
        self._on_connected()
        return True

    def ensure_connection(self) -> bool:
        """Return True if the connection is live, reconnecting if it went stale."""
        if not self.connected:
            return self.connect_to_autocad()
        try:
            _ = str(self.doc.Name)
            return True
        except Exception:
            self.connected = False
            return self.connect_to_autocad()

    def _on_connected(self) -> None:
        """Hook run after every successful connect. Mixins extend it via super()."""

    # ------------------------------------------------------------------ helpers

    def get_color_index(self, color: Color) -> int:
        """Resolve a colour name, ACI number, or numeric string to an ACI index."""
        if isinstance(color, int):
            return color
        if color is None:
            return config.DEFAULT_COLOR_INDEX
        text = str(color).strip().lower()
        if text.isdigit():
            return int(text)
        return self.color_map.get(text, config.DEFAULT_COLOR_INDEX)

    def set_entity_color(self, entity: Any, color: Color) -> None:
        """Apply a colour to an entity, ignoring failures."""
        try:
            entity.Color = self.get_color_index(color)
        except Exception:
            log.debug("Could not set entity colour", exc_info=True)

    def safe_operation(self, operation_func: Callable[[], Any], delay: float = config.OPERATION_DELAY) -> Any:
        """Run a COM operation followed by the pause AutoCAD needs; None on failure."""
        return call_with_delay(operation_func, delay)

    def regen(self) -> None:
        """Regenerate the active viewport, ignoring failures."""
        try:
            self.doc.Regen(config.AC_ACTIVE_VIEWPORT)
        except Exception:
            log.debug("Regen failed", exc_info=True)

    def add_to_model_space(self, factory: Callable[[Any], Any], color: Color) -> Optional[str]:
        """Create one entity, colour it, and regen.

        ``factory`` receives the ModelSpace collection and returns the new entity.
        Returns the entity handle, or None if AutoCAD did not confirm creation.
        """

        def operation() -> Any:
            entity = factory(self.doc.ModelSpace)
            self.set_entity_color(entity, color)
            self.regen()
            return entity

        entity = self.safe_operation(operation)
        return None if entity is None else handle_of(entity)
