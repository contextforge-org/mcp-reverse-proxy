# MCP Reverse Proxy Tests

This directory contains unit tests for the `mcp_reverse_proxy` package.

## Test Organization

The tests were moved from `tests/unit/mcpgateway/test_mcp_reverse_proxy_*` to this location because `mcp_reverse_proxy` is a standalone package, not a submodule of `mcpgateway`.

## Test Files

- `test_mcp_reverse_proxy_base.py` - Tests for base transport classes
- `test_mcp_reverse_proxy_cli.py` - Tests for CLI module
- `test_mcp_reverse_proxy_client.py` - Tests for reverse proxy client
- `test_mcp_reverse_proxy_sse_adapter.py` - Tests for SSE transport adapter
- `test_mcp_reverse_proxy_stdio_adapter.py` - Tests for stdio transport adapter
- `test_mcp_reverse_proxy_streamablehttp_adapter.py` - Tests for streamable HTTP transport adapter
- `test_mcp_reverse_proxy_websocket_adapter.py` - Tests for WebSocket transport adapter

## Running Tests
From the repository root:
```bash
pytest tests/
```

## Integration Tests

`tests/integration/` contains end-to-end tests that run the real transport adapters (stdio, SSE, Streamable HTTP) against a live FastMCP companion server (`companion_server.py`), plus a full reverse-proxy round-trip test using a fake in-process WebSocket gateway.

They require the `integration` optional extra:
```bash
pip install -e ".[dev,integration]"
pytest tests/integration/
```

Without the extra, the integration test modules are skipped automatically, so the unit-test suite runs unchanged. In CI they run as a separate non-blocking job.
## Import Changes

All imports have been updated from:
```python
from mcpgateway.mcp_reverse_proxy.* import ...
```

To:
```python
from mcp_reverse_proxy.* import ...
```

This reflects the correct package structure where `mcp_reverse_proxy` is a standalone package.