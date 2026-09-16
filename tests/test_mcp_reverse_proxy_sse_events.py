"""Location: ./mcp_reverse_proxy/tests/test_mcp_reverse_proxy_sse_events.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

Tests for the shared SSE event parser.
"""

# Future
from __future__ import annotations

# First-Party
from mcp_reverse_proxy.transports.sse_events import SSEParser, parse_sse_events


def test_parse_sse_events_skips_empty_keepalive_preamble() -> None:
    """Empty data frames and id/retry control fields must not shadow the JSON event."""
    text = 'data:\nid: 0\nretry: 3000\n\ndata: {"jsonrpc":"2.0","id":1}\n\n'
    events = parse_sse_events(text)
    assert [(e.event, e.data) for e in events] == [(None, '{"jsonrpc":"2.0","id":1}')]


def test_parse_sse_events_returns_every_event_in_order() -> None:
    """All dispatched events are returned, with their event names."""
    text = 'event: message\ndata: first\n\nevent: message\ndata: second\n\n'
    events = parse_sse_events(text)
    assert [(e.event, e.data) for e in events] == [("message", "first"), ("message", "second")]


def test_parse_sse_events_joins_multi_line_data_frames() -> None:
    """Multiple data lines of one event join with newlines (SSE spec)."""
    text = 'data: {"a":\ndata: 1}\n\n'
    events = parse_sse_events(text)
    assert [e.data for e in events] == ['{"a":\n1}']


def test_parse_sse_events_flushes_unterminated_trailing_event() -> None:
    """A final event without a closing blank line is still dispatched."""
    text = "data: tail"
    events = parse_sse_events(text)
    assert [e.data for e in events] == ["tail"]


def test_parse_sse_events_strips_crlf_endings() -> None:
    """CRLF line endings parse identically to LF."""
    text = 'data:\r\n\r\ndata: {"ok":true}\r\n\r\n'
    events = parse_sse_events(text)
    assert [e.data for e in events] == ['{"ok":true}']


def test_parse_sse_events_ignores_comments_and_blank_stream() -> None:
    """Comment-only or empty documents produce no events."""
    assert parse_sse_events(": ping\n\n: pong\n\n") == []
    assert parse_sse_events("") == []


def test_feed_line_is_incremental_and_reusable() -> None:
    """Feeding lines one at a time matches whole-document parsing."""
    parser = SSEParser()
    dispatched = []
    for line in ["event: message", 'data: {"jsonrpc": "2.0"}', "", "data:", "", 'data: {"x":1}', ""]:
        if (event := parser.feed_line(line)) is not None:
            dispatched.append(event)
    assert parser.flush() is None   # last blank line closed the final event
    assert [(e.event, e.data) for e in dispatched] == [
        ("message", '{"jsonrpc": "2.0"}'),
        (None, '{"x":1}'),
    ]
