"""Integration tests: sessionless 2026-07-28 (modern era) MCP traffic.

Drives the Streamable HTTP adapter against the live FastMCP 4 companion
server without an initialize handshake: ``server/discover`` for capability
discovery, then ordinary method calls carrying the protocol version in
``params._meta`` (the modern-era convention). Also verifies that a
modern-era 404 (unknown method) is relayed to the gateway as a JSON-RPC
error response rather than triggering the handshake-era session-expiry
recovery.
"""

# Future
from __future__ import annotations

# Standard
from typing import Any

# Third-Party
import pytest

# First-Party
from mcp_reverse_proxy.transports.streamablehttp_adapter import StreamableHttpAdapter
from tests.integration.helpers import (
    MODERN_PROTOCOL_META_KEY,
    MODERN_PROTOCOL_VERSION,
    MessageCollector,
    rpc_request,
)

pytest.importorskip("fastmcp", reason="requires the 'integration' extra (pip install -e '.[integration]')")
pytestmark = pytest.mark.integration


def modern_request(request_id: int, method: str, params: dict[str, Any] | None = None) -> str:
    """Serialize a modern-era JSON-RPC request carrying the protocol version in params._meta."""
    params = dict(params or {})
    params["_meta"] = {
        MODERN_PROTOCOL_META_KEY: MODERN_PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientInfo": {"name": "mcp-reverse-proxy-integration-tests", "version": "0.1.0"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    return rpc_request(request_id, method, params)


@pytest.fixture
def modern_collector(streamable_http_transport: StreamableHttpAdapter) -> MessageCollector:
    """Attach a MessageCollector to the sessionless transport."""
    message_collector = MessageCollector()
    streamable_http_transport.add_message_handler(message_collector)
    return message_collector


async def test_modern_era_sessionless_round_trip(
    streamable_http_transport: StreamableHttpAdapter, modern_collector: MessageCollector
) -> None:
    """Drive a full sessionless MCP exchange: discover, then calls, with no initialize."""
    adapter = streamable_http_transport

    # server/discover: capability discovery replaces the initialize handshake
    await adapter.send(modern_request(1, "server/discover"))
    response = await modern_collector.response_for(1)
    result = response["result"]
    assert MODERN_PROTOCOL_VERSION in result["supportedVersions"]
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "reverse-proxy-companion"
    assert "tools" in result["capabilities"]

    # The modern era must not mint a session
    assert adapter._sessionless is True
    assert adapter._session_id is None

    # tools/call
    await adapter.send(modern_request(2, "tools/call", {"name": "echo", "arguments": {"message": "hello-modern"}}))
    response = await modern_collector.response_for(2)
    assert any("hello-modern" in item.get("text", "") for item in response["result"]["content"])

    # tools/list
    await adapter.send(modern_request(3, "tools/list"))
    response = await modern_collector.response_for(3)
    tool_names = {tool["name"] for tool in response["result"]["tools"]}
    assert {"echo", "add"} <= tool_names

    # resources/read exercises the Mcp-Name: <uri> header path
    await adapter.send(modern_request(4, "resources/read", {"uri": "companion://info"}))
    response = await modern_collector.response_for(4)
    assert any("reverse-proxy-companion" in item.get("text", "") for item in response["result"]["contents"])

    # prompts/get exercises the Mcp-Name: <name> header path
    await adapter.send(modern_request(5, "prompts/get", {"name": "greet", "arguments": {"name": "proxy"}}))
    response = await modern_collector.response_for(5)
    assert "proxy" in str(response["result"])


async def test_modern_era_unknown_method_relays_jsonrpc_error(
    streamable_http_transport: StreamableHttpAdapter, modern_collector: MessageCollector
) -> None:
    """A modern-era unknown method returns 404 + -32601, relayed without session-expiry recovery."""
    adapter = streamable_http_transport

    await adapter.send(modern_request(1, "bogus/method"))
    response = await modern_collector.response_for(1)

    assert response["error"]["code"] == -32601
    # The failure must not be mistaken for handshake-era session expiry:
    # sessionless state is intact and no re-registration was triggered.
    assert adapter._sessionless is True
    assert adapter._protocol_version == MODERN_PROTOCOL_VERSION
