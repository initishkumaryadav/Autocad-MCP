"""Low-level helpers for talking to AutoCAD through pywin32 COM."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional, Sequence, TypeVar

import pythoncom
import win32com.client

log = logging.getLogger(__name__)

T = TypeVar("T")


def variant_point(x: float, y: float, z: float = 0.0) -> Any:
    """A 3D point as the VT_ARRAY|VT_R8 VARIANT that AutoCAD's Add* methods require."""
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x), float(y), float(z)])


def to_variant_point(point: Sequence[float]) -> Any:
    """Convert an [x, y] or [x, y, z] list into a VARIANT point (z defaults to 0)."""
    z = point[2] if len(point) > 2 else 0.0
    return variant_point(point[0], point[1], z)


def call_with_delay(func: Callable[[], T], delay: float) -> Optional[T]:
    """Run a COM operation, then pause; return None instead of raising.

    The pause happens on success *and* failure - AutoCAD needs it either way.
    """
    try:
        return func()
    except Exception:
        log.debug("COM operation failed", exc_info=True)
        return None
    finally:
        time.sleep(delay)


def try_get(func: Callable[[], T], default: T) -> T:
    """Read a COM property, falling back to ``default`` if the read fails."""
    try:
        return func()
    except Exception:
        return default


def handle_of(entity: Any) -> Optional[str]:
    """The entity's handle string, or None if it cannot be read."""
    try:
        return str(entity.Handle)
    except Exception:
        return None
