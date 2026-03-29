"""MCP client that uses the official MCP SDK's stdio transport.

Usage::

    async with open_mcp_client(["python", "-m", "athena_knowledge_mcp.server.app"]) as client:
        tools = await client.list_tools()
        result = await client.call_tool("list_athena_databases", {})
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)


class MCPClient:
    """Thin wrapper around ``ClientSession`` with convenience helpers."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._session.list_tools()
        return [t.model_dump() for t in result.tools]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        result = await self._session.call_tool(name, arguments or {})
        # Extract text content blocks
        texts: list[str] = []
        for block in result.content:
            if isinstance(block, types.TextContent):
                texts.append(block.text)
        if len(texts) == 1:
            try:
                return json.loads(texts[0])
            except (json.JSONDecodeError, TypeError):
                return texts[0]
        if texts:
            return texts
        return [b.model_dump() for b in result.content]


@asynccontextmanager
async def open_mcp_client(
    command: list[str],
    env: dict[str, str] | None = None,
):
    """Context manager that spawns the MCP server and yields an MCPClient."""
    server_params = StdioServerParameters(
        command=command[0],
        args=command[1:],
        env=env,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield MCPClient(session)
