#!/usr/bin/env python3
"""MCP server entry point: exposes ``AutoCADClient`` operations as MCP tools over stdio.

Run with ``python -m autocad_mcp.server`` (or ``python -m autocad_mcp`` /
the ``autocad-com-mcp`` console script).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from .autocad import AutoCADClient
from .config import SERVER_NAME, SERVER_VERSION
from .tools import TOOLS, TOOLS_BY_NAME

log = logging.getLogger(__name__)


def call_tool(client: AutoCADClient, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Dispatch one tool call to the client and return its result dict (never raises)."""
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return tool.handler(client, arguments or {})
    except KeyError as e:
        return {"error": f"Missing required argument for {name}: {e.args[0]}"}
    except Exception as e:
        log.exception("Tool %s failed", name)
        return {"error": f"Error calling tool {name}: {e}"}


def register_tools(server: Server, client: AutoCADClient) -> None:
    """Attach the list_tools / call_tool handlers for every tool in ``TOOLS``."""

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return [
            types.Tool(name=tool.name, description=tool.description, inputSchema=tool.input_schema)
            for tool in TOOLS
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
        # COM objects are bound to this thread's apartment, so calls run inline
        # rather than in a worker thread.
        result = call_tool(client, name, arguments)
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


class AutoCADCOMServer(AutoCADClient):
    """An ``AutoCADClient`` that also owns an MCP ``Server``.

    Kept so existing code (``from autocad_mcp.server import AutoCADCOMServer``)
    keeps working; new code can use ``AutoCADClient`` directly.
    """

    def __init__(self) -> None:
        super().__init__()
        self.server = Server(SERVER_NAME)

    def setup_tools(self) -> None:
        register_tools(self.server, self)


async def serve() -> None:
    """Connect to AutoCAD and serve MCP over stdio until the client disconnects."""
    app = AutoCADCOMServer()
    if not app.connect_to_autocad():
        log.warning("AutoCAD is not available yet; will retry on the first tool call")
    app.setup_tools()

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=SERVER_NAME,
                server_version=SERVER_VERSION,
                capabilities=app.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


def main() -> None:
    """Console-script entry point."""
    # stdout carries the MCP protocol, so logs must go to stderr.
    logging.basicConfig(
        stream=sys.stderr,
        level=os.environ.get("AUTOCAD_MCP_LOG_LEVEL", "WARNING").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(serve())


if __name__ == "__main__":
    main()
