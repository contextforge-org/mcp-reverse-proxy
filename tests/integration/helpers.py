"""Shared helpers for reverse-proxy integration tests."""

# Future
from __future__ import annotations

# Standard
import asyncio
import json
from typing import Any

# First-Party
from mcp_reverse_proxy.base import McpServerTransport
from mcp_reverse_proxy.transports.sse_adapter import SseAdapter

DEFAULT_TIMEOUT = 15.0

INITIALIZE_PARAMS: dict[str, Any] = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "mcp-reverse-proxy-integration-tests", "version": "0.1.0"},
}

INITIALIZED_NOTIFICATION = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})


def rpc_request(request_id: int, method: str, params: dict[str, Any] | None = None) -> str:
    """Serialize a JSON-RPC 2.0 request."""
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return json.dumps(message)


class MessageCollector:
    """Collect JSON-RPC messages dispatched by a transport adapter."""

    def __init__(self) -> None:
        """Initialize the collector with an empty queue."""
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def __call__(self, message: str) -> None:
        """Adapter message handler entry point."""
        await self.queue.put(json.loads(message))

    async def response_for(self, request_id: int, timeout: float = DEFAULT_TIMEOUT) -> dict[str, Any]:
        """Return the first queued message whose ``id`` equals request_id."""
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"no response received for request id={request_id}")
            message = await asyncio.wait_for(self.queue.get(), remaining)
            if message.get("id") == request_id:
                return message


async def wait_until_ready(adapter: McpServerTransport, timeout: float = DEFAULT_TIMEOUT) -> None:
    """Wait until the transport is ready to accept MCP messages.

    The SSE adapter learns its message endpoint asynchronously from the
    server's ``endpoint`` event; stdio and Streamable HTTP are ready as soon
    as ``start()`` returns.
    """
    if not isinstance(adapter, SseAdapter):
        return
    deadline = asyncio.get_running_loop().time() + timeout
    while adapter._message_endpoint is None:
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError("SSE endpoint event not received from companion server")
        await asyncio.sleep(0.05)
