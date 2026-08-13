"""Integration tests: transport adapters against the live companion server.

Each MCP-server-side transport (stdio, SSE, Streamable HTTP) is driven
through a full MCP session - initialize, initialized notification,
tools/list, tools/call, resources/list - against the FastMCP companion
server (issue #2).
"""

# Future
from __future__ import annotations

# Third-Party
import pytest

# First-Party
from mcp_reverse_proxy.base import McpServerTransport
from tests.integration.helpers import (
    INITIALIZE_PARAMS,
    INITIALIZED_NOTIFICATION,
    MessageCollector,
    rpc_request,
    wait_until_ready,
)

pytest.importorskip("fastmcp", reason="requires the 'integration' extra (pip install -e '.[integration]')")
pytestmark = pytest.mark.integration


async def test_full_mcp_session_round_trip(mcp_transport: McpServerTransport, collector: MessageCollector) -> None:
    """Drive a complete MCP session over the parametrized transport."""
    await wait_until_ready(mcp_transport)

    # initialize
    await mcp_transport.send(rpc_request(1, "initialize", INITIALIZE_PARAMS))
    response = await collector.response_for(1)
    assert response["result"]["serverInfo"]["name"] == "reverse-proxy-companion"

    # notifications/initialized
    await mcp_transport.send(INITIALIZED_NOTIFICATION)

    # tools/list
    await mcp_transport.send(rpc_request(2, "tools/list"))
    response = await collector.response_for(2)
    tool_names = {tool["name"] for tool in response["result"]["tools"]}
    assert {"echo", "add"} <= tool_names

    # tools/call: echo
    await mcp_transport.send(rpc_request(3, "tools/call", {"name": "echo", "arguments": {"message": "hello-proxy"}}))
    response = await collector.response_for(3)
    assert any("hello-proxy" in item.get("text", "") for item in response["result"]["content"])

    # tools/call: add
    await mcp_transport.send(rpc_request(4, "tools/call", {"name": "add", "arguments": {"a": 2, "b": 40}}))
    response = await collector.response_for(4)
    assert any("42" in item.get("text", "") for item in response["result"]["content"])

    # resources/list
    await mcp_transport.send(rpc_request(5, "resources/list"))
    response = await collector.response_for(5)
    uris = {resource["uri"] for resource in response["result"]["resources"]}
    assert "companion://info" in uris
