"""AutoCAD MCP server: drive AutoCAD over COM from MCP clients."""

from .autocad import AutoCADClient
from .config import SERVER_VERSION as __version__

__all__ = ["AutoCADClient", "__version__"]
