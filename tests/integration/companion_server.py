"""Companion MCP server for reverse-proxy integration tests.

A minimal FastMCP server exposing deterministic tools, a resource, and a
prompt over stdio, SSE, and Streamable HTTP. It is the minimal equivalent of
``tests/mcp-servers/python/test_reverse_proxy_mcp_server/`` from the
mcp-context-forge repository (see issue #2), small enough to live in-tree and
run as a pytest fixture.
"""

# Future
from __future__ import annotations

# Standard
import argparse
import platform
from typing import Literal

# Third-Party (integration extra)
from fastmcp import FastMCP
from starlette.applications import Starlette

def create_server() -> FastMCP:
    """Build a fresh companion FastMCP instance.

    Each HTTP test must get its own instance: FastMCP 4 / mcp 2.x bind
    lifespan and session state to the instance on the running event loop,
    so reusing one instance across tests (each test runs on its own loop)
    lets state from a previous test's loop break the next app's responses
    ("ASGI callable returned without completing response").
    """
    server = FastMCP("reverse-proxy-companion")

    @server.tool()
    def echo(message: str) -> str:
        """Echo the message back verbatim."""
        return message

    @server.tool()
    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    @server.resource("companion://info")
    def server_info() -> str:
        """Static resource identifying the companion server."""
        return f"reverse-proxy-companion on Python {platform.python_version()}"

    @server.prompt()
    def greet(name: str) -> str:
        """Return a greeting prompt for the given name."""
        return f"Say hello to {name}."

    return server


mcp = create_server()


def create_app(transport: Literal["sse", "streamable-http"]) -> Starlette:
    """Build the ASGI app for an HTTP transport on a fresh server instance."""
    return create_server().http_app(transport=transport)


def main() -> None:
    """Launch the companion server from the command line."""
    parser = argparse.ArgumentParser(description="Reverse-proxy companion test MCP server")
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port, show_banner=False)


if __name__ == "__main__":
    main()
