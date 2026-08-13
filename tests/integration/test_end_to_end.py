"""End-to-end integration test for the reverse proxy (issue #2).

Bridges the live FastMCP companion server (stdio) through ReverseProxyClient
to a fake in-process WebSocket gateway, verifying registration and a full
request/response round-trip from gateway to MCP server and back.
"""

# Future
from __future__ import annotations

# Standard
import asyncio
import json
from typing import Any

# Third-Party
import pytest
from websockets.asyncio.server import ServerConnection, serve

# First-Party
from mcp_reverse_proxy.client import ReverseProxyClient
from mcp_reverse_proxy.transports.stdio_adapter import StdioAdapter
from mcp_reverse_proxy.transports.websocket_adapter import WebSocketAdapter
from tests.integration.helpers import INITIALIZE_PARAMS, rpc_request

pytest.importorskip("fastmcp", reason="requires the 'integration' extra (pip install -e '.[integration]')")
pytestmark = pytest.mark.integration

GATEWAY_TIMEOUT = 30.0
SESSION_ID = "integration-e2e"


async def test_reverse_proxy_end_to_end_stdio(companion_stdio_command: str) -> None:
    """Exercise client + stdio adapter + WebSocket adapter against real MCP server and fake gateway."""
    loop = asyncio.get_running_loop()
    registered: asyncio.Future[str] = loop.create_future()
    tool_result: asyncio.Future[dict[str, Any]] = loop.create_future()

    async def gateway_handler(websocket: ServerConnection) -> None:
        async for raw in websocket:
            message = json.loads(raw)
            msg_type = message.get("type")

            if msg_type == "register":
                session_id = message["sessionId"]
                await websocket.send(json.dumps({"type": "register_ack", "sessionId": session_id, "status": "received"}))
                await websocket.send(json.dumps({"type": "register_complete", "sessionId": session_id, "status": "success"}))
                if not registered.done():
                    registered.set_result(session_id)
                # Drive an MCP session through the proxy, as the real gateway would
                await websocket.send(
                    json.dumps(
                        {
                            "type": "request",
                            "sessionId": session_id,
                            "payload": json.loads(rpc_request(1, "initialize", INITIALIZE_PARAMS)),
                        }
                    )
                )
            elif msg_type == "response":
                payload = message.get("payload", {})
                session_id = message["sessionId"]
                if payload.get("id") == 1:
                    # initialize complete: send initialized notification, then a tool call
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "request",
                                "sessionId": session_id,
                                "payload": {"jsonrpc": "2.0", "method": "notifications/initialized"},
                            }
                        )
                    )
                    await websocket.send(
                        json.dumps(
                            {
                                "type": "request",
                                "sessionId": session_id,
                                "payload": json.loads(
                                    rpc_request(2, "tools/call", {"name": "echo", "arguments": {"message": "end-to-end"}})
                                ),
                            }
                        )
                    )
                elif payload.get("id") == 2 and not tool_result.done():
                    tool_result.set_result(payload)

    async with serve(gateway_handler, "127.0.0.1", 0) as gateway:
        port = gateway.sockets[0].getsockname()[1]
        client = ReverseProxyClient(
            mcp_transport=StdioAdapter(companion_stdio_command),
            gateway_transport=WebSocketAdapter(gateway_url=f"ws://127.0.0.1:{port}", session_id=SESSION_ID),
            session_id=SESSION_ID,
            keepalive_interval=60.0,
        )
        await client.connect()
        try:
            assert await asyncio.wait_for(registered, GATEWAY_TIMEOUT) == SESSION_ID
            payload = await asyncio.wait_for(tool_result, GATEWAY_TIMEOUT)
            assert any("end-to-end" in item.get("text", "") for item in payload["result"]["content"])
        finally:
            await client.disconnect()
