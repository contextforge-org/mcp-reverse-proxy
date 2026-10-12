"""Location: ./mcp_reverse_proxy/tests/test_mcp_reverse_proxy_streamablehttp_adapter.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

Unit tests for the streamable HTTP reverse proxy transport adapter.
"""

# Future
from __future__ import annotations

# Standard
import asyncio
import json
import ssl
from unittest.mock import AsyncMock, Mock, call

# Third-Party
import httpx
import pytest

# First-Party
from mcp_reverse_proxy.transports.streamablehttp_adapter import (
    SessionExpiredError,
    StreamableHttpAdapter,
    encode_header_value,
    extract_modern_protocol_version,
)


@pytest.mark.asyncio
async def test_start_creates_http_client_sets_endpoint_and_receive_task(monkeypatch) -> None:
    """Start should initialize the client, message endpoint, and receive task."""
    created_tasks: list[asyncio.Task[None]] = []

    class FakeClient:
        """Minimal async client fake."""

        async def aclose(self) -> None:
            """No-op close."""

    async_client_mock = Mock(return_value=FakeClient())
    original_create_task = asyncio.create_task

    def capture_task(coro):
        task = original_create_task(coro)
        created_tasks.append(task)
        return task

    monkeypatch.setattr("mcp_reverse_proxy.transports.streamablehttp_adapter.httpx.AsyncClient", async_client_mock)
    monkeypatch.setattr("mcp_reverse_proxy.transports.streamablehttp_adapter.asyncio.create_task", capture_task)

    adapter = StreamableHttpAdapter("http://server.example/mcp", timeout=12.5)

    await adapter.start()

    assert adapter._connected is True
    assert adapter._message_endpoint == "http://server.example/mcp"
    assert async_client_mock.call_args.kwargs["http2"] is True
    assert async_client_mock.call_args.kwargs["verify"] is False
    assert isinstance(async_client_mock.call_args.kwargs["timeout"], httpx.Timeout)
    assert adapter._receive_task is created_tasks[0]

    adapter._receive_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await adapter._receive_task


@pytest.mark.asyncio
async def test_start_configures_https_ssl_context_with_custom_cert(monkeypatch) -> None:
    """HTTPS start should use an SSL context created from the provided CA data."""
    fake_ssl_context = Mock(spec=ssl.SSLContext)
    fake_ssl_context.check_hostname = True
    fake_ssl_context.verify_mode = ssl.CERT_REQUIRED
    fake_ssl_context.load_verify_locations = Mock()  # Mock the load_verify_locations method
    receive_task = asyncio.create_task(asyncio.sleep(10))
    async_client_mock = Mock()

    # Mock load_cert_data to return test certificate data
    test_cert_data = "MOCK_CERT_DATA"
    monkeypatch.setattr("mcp_reverse_proxy.transports.streamablehttp_adapter.load_cert_data",
                        lambda _cert: test_cert_data)

    # Mock SSLContext constructor to return our fake context
    monkeypatch.setattr("mcp_reverse_proxy.transports.streamablehttp_adapter.ssl.SSLContext",
                        lambda _protocol: fake_ssl_context)
    monkeypatch.setattr("mcp_reverse_proxy.transports.streamablehttp_adapter.httpx.AsyncClient", async_client_mock)
    monkeypatch.setattr(
        "mcp_reverse_proxy.transports.streamablehttp_adapter.asyncio.create_task",
        Mock(return_value=receive_task),
    )

    adapter = StreamableHttpAdapter("https://secure.example/mcp", cert="test_cert_input")

    await adapter.start()

    # Verify load_verify_locations was called with the cert data
    fake_ssl_context.load_verify_locations.assert_called_once_with(cadata=test_cert_data)
    assert async_client_mock.call_args.kwargs["verify"] is fake_ssl_context
    assert fake_ssl_context.check_hostname is True
    assert fake_ssl_context.verify_mode == ssl.CERT_REQUIRED

    receive_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await receive_task


@pytest.mark.asyncio
async def test_stop_cancels_task_closes_client_and_clears_session_state() -> None:
    """Stop should cancel the receive task, close the client, and clear session state."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._session_id = "session-1"
    adapter._message_endpoint = "http://server.example/mcp"
    adapter._protocol_version = "2025-11-05"
    adapter._sessionless = True
    adapter._receive_task = asyncio.create_task(asyncio.sleep(10))
    adapter._client = AsyncMock()

    await adapter.stop()

    assert adapter._connected is False
    assert adapter._session_id is None
    assert adapter._message_endpoint is None
    assert adapter._protocol_version is None
    assert adapter._sessionless is False
    assert adapter._client is None


@pytest.mark.asyncio
async def test_send_initialize_stores_session_protocol_and_notifies_handlers() -> None:
    """Initialize response should set session state and forward inline JSON responses."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    handler = AsyncMock()
    adapter.add_message_handler(handler)

    response = Mock()
    response.headers = {"mcp-session-id": "session-1"}
    response.status_code = 200
    response.content = b'{"jsonrpc":"2.0","result":{"protocolVersion":"2025-11-05"}}'
    response.text = '{"jsonrpc":"2.0","result":{"protocolVersion":"2025-11-05"}}'
    response.raise_for_status = Mock()
    adapter._client.post = AsyncMock(return_value=response)

    await adapter.send('{"jsonrpc":"2.0","id":1,"method":"initialize"}')

    assert adapter._session_id == "session-1"
    assert adapter._protocol_version == "2025-11-05"
    handler.assert_awaited_once_with('{"jsonrpc":"2.0","result":{"protocolVersion":"2025-11-05"}}')
    headers = adapter._client.post.await_args.kwargs["headers"]
    assert "mcp-session-id" not in headers
    assert "mcp-protocol-version" not in headers


@pytest.mark.asyncio
async def test_send_with_existing_session_adds_session_headers_and_parses_sse_response() -> None:
    """Established sessions should send MCP headers and parse SSE-formatted inline responses."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    adapter._session_id = "session-1"
    adapter._protocol_version = "2025-11-05"
    adapter._auth_headers = {"Authorization": "Bearer token"}
    handler = AsyncMock()
    adapter.add_message_handler(handler)

    response = Mock()
    response.headers = {}
    response.status_code = 200
    response.content = b'event: message\ndata: {"jsonrpc":"2.0","id":2,"result":{"ok":true}}\n\n'
    response.text = 'event: message\ndata: {"jsonrpc":"2.0","id":2,"result":{"ok":true}}\n\n'
    response.raise_for_status = Mock()
    adapter._client.post = AsyncMock(return_value=response)

    await adapter.send('{"jsonrpc":"2.0","id":2,"method":"tools/call"}')

    handler.assert_awaited_once_with('{"jsonrpc":"2.0","id":2,"result":{"ok":true}}')
    headers = adapter._client.post.await_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer token"
    assert headers["mcp-session-id"] == "session-1"
    assert headers["mcp-protocol-version"] == "2025-11-05"


@pytest.mark.asyncio
async def test_send_relays_json_after_empty_sse_keepalive_preamble() -> None:
    """SSE preamble frames must not shadow the JSON event that follows.

    Regression: servers open the stream with ``data:`` (empty payload), ``id:``
    and ``retry:`` control frames before the JSON event. The old parser took
    the FIRST ``data:`` line - an empty string - so handlers received "" and
    downstream JSON parsing failed with "Input is a zero-length, empty
    document" and the initialize response was never relayed.
    """
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    handler = AsyncMock()
    adapter.add_message_handler(handler)

    initialize_result = '{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2025-11-05"}}'
    response = Mock()
    response.headers = {"mcp-session-id": "session-1"}
    response.status_code = 200
    response.content = b"data:\nid: 0\nretry: 3000\n\ndata: " + initialize_result.encode() + b"\n\n"
    response.text = f"data:\nid: 0\nretry: 3000\n\ndata: {initialize_result}\n\n"
    response.raise_for_status = Mock()
    adapter._client.post = AsyncMock(return_value=response)

    await adapter.send('{"jsonrpc":"2.0","id":1,"method":"initialize"}')

    handler.assert_awaited_once_with(initialize_result)
    assert adapter._protocol_version == "2025-11-05"


@pytest.mark.asyncio
async def test_send_relays_every_sse_event_in_multi_event_response() -> None:
    """Each dispatched SSE event must be relayed, not just the first data frame."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    adapter._session_id = "session-1"
    adapter._protocol_version = "2025-11-05"
    handler = AsyncMock()
    adapter.add_message_handler(handler)

    first = '{"jsonrpc":"2.0","id":2,"result":{"ok":true}}'
    second = '{"jsonrpc":"2.0","id":3,"result":{"ok":false}}'
    response = Mock()
    response.headers = {}
    response.status_code = 200
    response.content = b"event: message\ndata: " + first.encode() + b"\n\ndata: " + second.encode() + b"\n\n"
    response.text = f"event: message\ndata: {first}\n\ndata: {second}\n\n"
    response.raise_for_status = Mock()
    adapter._client.post = AsyncMock(return_value=response)

    await adapter.send('{"jsonrpc":"2.0","id":2,"method":"tools/call"}')

    assert handler.await_args_list == [call(first), call(second)]


@pytest.mark.asyncio
async def test_send_joins_multi_line_sse_data_frames() -> None:
    """Multi-line ``data:`` frames must be joined with newlines per the SSE spec."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    adapter._session_id = "session-1"
    adapter._protocol_version = "2025-11-05"
    handler = AsyncMock()
    adapter.add_message_handler(handler)

    response = Mock()
    response.headers = {}
    response.status_code = 200
    response.content = b'data: {"jsonrpc":"2.0","id":7,\ndata: "result":{"ok":true}}\n\n'
    response.text = 'data: {"jsonrpc":"2.0","id":7,\ndata: "result":{"ok":true}}\n\n'
    response.raise_for_status = Mock()
    adapter._client.post = AsyncMock(return_value=response)

    await adapter.send('{"jsonrpc":"2.0","id":7,"method":"tools/call"}')

    handler.assert_awaited_once_with('{"jsonrpc":"2.0","id":7,\n"result":{"ok":true}}')


@pytest.mark.asyncio
async def test_send_retries_initialize_after_404_and_parses_sse_preamble() -> None:
    """The 404-retry path must parse SSE bodies the same way as the primary path."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    adapter._session_id = "stale-session"
    adapter._protocol_version = "2025-11-05"
    handler = AsyncMock()
    adapter.add_message_handler(handler)

    ok_body = Mock()
    ok_body.headers = {"mcp-session-id": "session-2"}
    ok_body.status_code = 200
    ok_body.content = b"data:\nid: 0\nretry: 3000\n\ndata: " + b'{"jsonrpc":"2.0","result":{"protocolVersion":"2025-11-05"}}' + b"\n\n"
    ok_body.text = 'data:\nid: 0\nretry: 3000\n\ndata: {"jsonrpc":"2.0","result":{"protocolVersion":"2025-11-05"}}\n\n'
    ok_body.raise_for_status = Mock()

    not_found = Mock()
    not_found.response = httpx.Response(404, request=httpx.Request("POST", "http://server.example/mcp"))
    adapter._client.post = AsyncMock(side_effect=[httpx.HTTPStatusError("404", request=not_found.response, response=not_found.response), ok_body])

    await adapter.send('{"jsonrpc":"2.0","id":1,"method":"initialize"}')

    handler.assert_awaited_once_with('{"jsonrpc":"2.0","result":{"protocolVersion":"2025-11-05"}}')
    assert adapter._session_id == "session-2"

@pytest.mark.asyncio
async def test_send_raises_for_non_initialize_request_without_session() -> None:
    """Non-initialize messages without a session should fail fast."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()

    with pytest.raises(RuntimeError, match="No valid session"):
        await adapter.send('{"jsonrpc":"2.0","id":2,"method":"tools/call"}')


@pytest.mark.asyncio
async def test_send_raises_runtime_error_when_not_connected() -> None:
    """Send should fail if the HTTP client connection has not been started."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")

    with pytest.raises(RuntimeError, match="Not connected to MCP server"):
        await adapter.send('{"jsonrpc":"2.0","id":1}')


@pytest.mark.asyncio
async def test_send_retries_initialize_after_404_and_updates_session_state() -> None:
    """Initialize requests should retry once without session headers after a 404."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    adapter._session_id = "stale-session"
    adapter._protocol_version = "old-version"
    handler = AsyncMock()
    adapter.add_message_handler(handler)

    request = httpx.Request("POST", "http://server.example/mcp")
    first_response = httpx.Response(404, request=request)
    http_error = httpx.HTTPStatusError("missing", request=request, response=first_response)

    retry_response = Mock()
    retry_response.headers = {"mcp-session-id": "new-session"}
    retry_response.status_code = 200
    retry_response.content = b'{"jsonrpc":"2.0","result":{"protocolVersion":"2025-11-05"}}'
    retry_response.text = '{"jsonrpc":"2.0","result":{"protocolVersion":"2025-11-05"}}'
    retry_response.raise_for_status = Mock()

    adapter._client.post = AsyncMock(side_effect=[http_error, retry_response])

    await adapter.send('{"jsonrpc":"2.0","id":1,"method":"initialize"}')

    assert adapter._session_id == "new-session"
    assert adapter._protocol_version == "2025-11-05"
    assert adapter._client.post.await_count == 2
    handler.assert_awaited_once_with('{"jsonrpc":"2.0","result":{"protocolVersion":"2025-11-05"}}')


@pytest.mark.asyncio
async def test_send_raises_session_expired_for_non_initialize_404() -> None:
    """Non-initialize 404 responses should clear session state and raise SessionExpiredError."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    adapter._session_id = "session-1"
    adapter._protocol_version = "2025-11-05"

    request = httpx.Request("POST", "http://server.example/mcp")
    response = httpx.Response(404, request=request)
    http_error = httpx.HTTPStatusError("missing", request=request, response=response)
    adapter._client.post = AsyncMock(side_effect=http_error)

    with pytest.raises(SessionExpiredError, match="session expired"):
        await adapter.send('{"jsonrpc":"2.0","id":2,"method":"tools/call"}')

    assert adapter._session_id is None
    assert adapter._protocol_version is None


@pytest.mark.asyncio
async def test_send_wraps_generic_http_error() -> None:
    """Non-status HTTP client failures should be wrapped in RuntimeError."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()

    request = httpx.Request("POST", "http://server.example/mcp")
    adapter._client.post = AsyncMock(side_effect=httpx.ConnectError("boom", request=request))

    with pytest.raises(RuntimeError, match="Failed to send message"):
        await adapter.send('{"jsonrpc":"2.0","id":1,"method":"initialize"}')


def test_set_authentication_supports_basic_bearer_and_passthrough_headers() -> None:
    """Authentication helper should normalize supported auth styles."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")

    adapter.set_authentication({"username": "alice", "password": "secret"}, "basic")
    assert adapter._auth_headers == {"Authorization": "Basic YWxpY2U6c2VjcmV0"}

    adapter.set_authentication({"token": "abc123"}, "bearer")
    assert adapter._auth_headers == {"Authorization": "Bearer abc123"}

    adapter.set_authentication({"X-Api-Key": "key"}, "custom")
    assert adapter._auth_headers == {"X-Api-Key": "key"}


@pytest.mark.asyncio
async def test_receive_stream_sleeps_until_cancelled(monkeypatch) -> None:
    """Receive loop should keep sleeping while connected and propagate cancellation."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    call_count = 0

    async def fake_sleep(_delay: float) -> None:
        nonlocal call_count
        call_count += 1
        raise asyncio.CancelledError

    monkeypatch.setattr("mcp_reverse_proxy.transports.streamablehttp_adapter.asyncio.sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await adapter._receive_stream()

    assert call_count == 1


def _modern_request(method: str, params: dict | None = None, request_id: int = 1) -> str:
    """Build a modern-era (2026-07-28) JSON-RPC request carrying the version in params._meta."""
    params = dict(params or {})
    params["_meta"] = {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}
    return json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})


def _mock_response(status_code: int = 200, body: str = '{"jsonrpc":"2.0","id":1,"result":{}}', headers: dict | None = None) -> Mock:
    """Build a mock httpx response for adapter send tests."""
    response = Mock()
    response.headers = headers or {}
    response.status_code = status_code
    response.content = body.encode()
    response.text = body
    response.raise_for_status = Mock()
    return response


def test_extract_modern_protocol_version_reads_params_meta_and_fallbacks() -> None:
    """The version lives in params._meta per spec; top-level _meta is a tolerated fallback."""
    assert extract_modern_protocol_version({"params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}}}) == "2026-07-28"
    assert extract_modern_protocol_version({"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28"}}) == "2026-07-28"
    assert extract_modern_protocol_version({"params": {"name": "echo"}}) is None
    assert extract_modern_protocol_version({"params": None}) is None
    assert extract_modern_protocol_version({}) is None


def test_encode_header_value_passes_safe_values_and_encodes_unsafe() -> None:
    """Header-safe ASCII passes through; everything else takes the =?base64?...?= sentinel."""
    assert encode_header_value("get_weather") == "get_weather"
    assert encode_header_value("companion://info") == "companion://info"

    encoded_unicode = encode_header_value("Hello, 世界")
    assert encoded_unicode == "=?base64?SGVsbG8sIOS4lueVjA==?="

    # Leading/trailing whitespace and sentinel-pattern values must be encoded
    assert encode_header_value(" padded ") == "=?base64?IHBhZGRlZCA=?="
    assert encode_header_value("=?base64?literal?=") == "=?base64?PT9iYXNlNjQ/bGl0ZXJhbD89?="

    # Control characters are not header-safe
    assert encode_header_value("line1\nline2") == "=?base64?bGluZTEKbGluZTI=?="


@pytest.mark.asyncio
async def test_send_modern_era_mints_version_and_routing_headers() -> None:
    """Sessionless send must mint MCP-Protocol-Version, Mcp-Method, and Mcp-Name per request."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    handler = AsyncMock()
    adapter.add_message_handler(handler)
    adapter._client.post = AsyncMock(return_value=_mock_response())

    await adapter.send(_modern_request("tools/call", {"name": "echo", "arguments": {"message": "hi"}}))

    assert adapter._sessionless is True
    assert adapter._protocol_version == "2026-07-28"
    headers = adapter._client.post.await_args.kwargs["headers"]
    assert headers["MCP-Protocol-Version"] == "2026-07-28"
    assert headers["Mcp-Method"] == "tools/call"
    assert headers["Mcp-Name"] == "echo"
    assert "mcp-session-id" not in headers
    assert "mcp-protocol-version" not in headers
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_server_discover_without_meta_enters_sessionless_mode() -> None:
    """server/discover opens the modern era even without _meta; unknown version means no version header."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    adapter._client.post = AsyncMock(return_value=_mock_response())

    await adapter.send('{"jsonrpc":"2.0","id":1,"method":"server/discover"}')

    assert adapter._sessionless is True
    headers = adapter._client.post.await_args.kwargs["headers"]
    assert headers["Mcp-Method"] == "server/discover"
    assert "MCP-Protocol-Version" not in headers


@pytest.mark.asyncio
async def test_send_sessionless_relays_404_jsonrpc_error_without_session_expiry() -> None:
    """Modern-era 404 (method not found) is relayed as a response, never as SessionExpiredError."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    handler = AsyncMock()
    adapter.add_message_handler(handler)

    error_body = '{"jsonrpc":"2.0","id":9,"error":{"code":-32601,"message":"Method not found"}}'
    adapter._client.post = AsyncMock(return_value=_mock_response(status_code=404, body=error_body))

    await adapter.send(_modern_request("bogus/method", request_id=9))

    handler.assert_awaited_once_with(error_body)
    assert adapter._sessionless is True
    assert adapter._protocol_version == "2026-07-28"


@pytest.mark.asyncio
async def test_send_sessionless_raises_on_bodyless_error_response() -> None:
    """A modern-era error status with no body is a transport failure, not a relayable response."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()

    response = _mock_response(status_code=500)
    response.content = b""
    adapter._client.post = AsyncMock(return_value=response)

    with pytest.raises(RuntimeError, match="HTTP 500"):
        await adapter.send(_modern_request("tools/list"))


@pytest.mark.asyncio
async def test_send_with_existing_session_ignores_meta_and_keeps_handshake_era() -> None:
    """A _meta version on a message must not flip an established handshake session to sessionless."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    adapter._session_id = "session-1"
    adapter._protocol_version = "2025-11-25"
    adapter._client.post = AsyncMock(return_value=_mock_response())

    await adapter.send(_modern_request("tools/call", {"name": "echo"}))

    assert adapter._sessionless is False
    headers = adapter._client.post.await_args.kwargs["headers"]
    assert headers["mcp-session-id"] == "session-1"
    assert headers["mcp-protocol-version"] == "2025-11-25"
    assert "Mcp-Method" not in headers


@pytest.mark.asyncio
async def test_send_sessionless_ignores_server_minted_session_id() -> None:
    """A session id on a modern-era response must not flip the adapter into handshake mode."""
    adapter = StreamableHttpAdapter("http://server.example/mcp")
    adapter._connected = True
    adapter._client = AsyncMock()
    adapter._client.post = AsyncMock(return_value=_mock_response(headers={"mcp-session-id": "rogue-session"}))

    await adapter.send(_modern_request("tools/list"))
    await adapter.send(_modern_request("tools/list", request_id=2))

    assert adapter._session_id is None
    for post_call in adapter._client.post.await_args_list:
        assert "mcp-session-id" not in post_call.kwargs["headers"]
