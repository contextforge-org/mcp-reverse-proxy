"""Fixtures for reverse-proxy integration tests (issue #2).

These tests exercise the real transport adapters against a live FastMCP
companion server. They require the ``integration`` optional dependency extra
(``pip install -e ".[integration]"``); the test modules skip cleanly when it
is not installed, so the unit-test suite is unaffected.
"""

# Future
from __future__ import annotations

# Standard
import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

# Third-Party
import pytest

# First-Party
from mcp_reverse_proxy.base import McpServerTransport
from mcp_reverse_proxy.transports.sse_adapter import SseAdapter
from mcp_reverse_proxy.transports.stdio_adapter import StdioAdapter
from mcp_reverse_proxy.transports.streamablehttp_adapter import StreamableHttpAdapter
from tests.integration.helpers import MessageCollector

COMPANION_SERVER = Path(__file__).parent / "companion_server.py"

SERVER_STARTUP_TIMEOUT = 10.0


@asynccontextmanager
async def _running_companion_http(kind: str) -> AsyncIterator[str]:
    """Run the companion server over an HTTP transport; yield its base URL."""
    # Third-Party (integration extra, imported lazily so unit-only installs can collect this file)
    import uvicorn

    from tests.integration.companion_server import create_app

    config = uvicorn.Config(create_app(kind), host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    serve_task = asyncio.create_task(server.serve())

    deadline = asyncio.get_running_loop().time() + SERVER_STARTUP_TIMEOUT
    while not server.started:
        if asyncio.get_running_loop().time() > deadline:
            serve_task.cancel()
            pytest.fail(f"companion server ({kind}) failed to start within {SERVER_STARTUP_TIMEOUT}s")
        await asyncio.sleep(0.05)

    port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await serve_task


@pytest.fixture
def companion_stdio_command() -> str:
    """Command line that launches the companion server over stdio."""
    return f"{sys.executable} {COMPANION_SERVER} --transport stdio"


@pytest.fixture(params=["stdio", "sse", "streamable-http"])
async def mcp_transport(request: pytest.FixtureRequest, companion_stdio_command: str) -> AsyncIterator[McpServerTransport]:
    """Start each MCP-server-side transport against the live companion server."""
    kind: str = request.param

    if kind == "stdio":
        adapter: McpServerTransport = StdioAdapter(companion_stdio_command)
        await adapter.start()
        try:
            yield adapter
        finally:
            await adapter.stop()
        return

    async with _running_companion_http(kind) as base_url:
        adapter = SseAdapter(f"{base_url}/sse") if kind == "sse" else StreamableHttpAdapter(f"{base_url}/mcp")
        await adapter.start()
        try:
            yield adapter
        finally:
            await adapter.stop()


@pytest.fixture
async def streamable_http_transport() -> AsyncIterator[StreamableHttpAdapter]:
    """Companion server over Streamable HTTP only (for protocol-era tests)."""
    async with _running_companion_http("streamable-http") as base_url:
        adapter = StreamableHttpAdapter(f"{base_url}/mcp")
        await adapter.start()
        try:
            yield adapter
        finally:
            await adapter.stop()


@pytest.fixture
def collector(mcp_transport: McpServerTransport) -> MessageCollector:
    """Attach a MessageCollector to the running transport."""
    message_collector = MessageCollector()
    mcp_transport.add_message_handler(message_collector)
    return message_collector
