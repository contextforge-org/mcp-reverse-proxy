"""Location: ./mcp_reverse_proxy/transports/sse_events.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

Shared Server-Sent Events (SSE) line parser for the transport adapters.

One implementation of the SSE line protocol (WHATWG server-sent events):

- ``data:`` lines accumulate for the current event; a blank line dispatches
  the event with its data lines joined by newlines.
- ``event:`` names the event; ``id:``/``retry:`` and ``:comment`` lines are
  control information and are ignored.
- Events whose accumulated data is empty are skipped: servers may open a
  stream with an empty ``data:`` keepalive frame before any JSON.
- ``flush()`` dispatches a trailing event not terminated by a blank line
  (common for inline HTTP responses whose body lacks a closing newline).
"""

# Future
from __future__ import annotations

# Standard
from typing import NamedTuple


class SseEvent(NamedTuple):
    """A single dispatched SSE event."""

    event: str | None   # event name (``event:`` field); None when unset
    data: str           # joined data lines, stripped; never empty


class SSEParser:
    """Incremental SSE parser fed one line at a time.

    Feed every line of the stream; ``feed_line`` returns the completed event
    when a blank line closes it, else ``None``. Call ``flush`` once after the
    last line to pick up an unterminated trailing event.
    """

    def __init__(self) -> None:
        """Initialize with no event in progress."""
        self._event: str | None = None
        self._data_lines: list[str] = []

    def feed_line(self, line: str) -> SseEvent | None:
        """Consume one line and return the event it completes, if any."""
        stripped = line.strip()   # also drops the trailing CR of CRLF endings
        if not stripped:
            return self._dispatch()
        if stripped.startswith("data:"):
            self._data_lines.append(stripped[5:].strip())
        elif stripped.startswith("event:"):
            self._event = stripped[6:].strip()
        # ``id:``, ``retry:`` and ``:comment`` lines are ignored.
        return None

    def flush(self) -> SseEvent | None:
        """Dispatch a trailing event not terminated by a blank line."""
        return self._dispatch()

    def _dispatch(self) -> SseEvent | None:
        """Close the in-progress event; empty payloads are skipped."""
        event, self._event = self._event, None
        data_lines, self._data_lines = self._data_lines, []
        if not data_lines:
            return None
        data = "\n".join(data_lines)
        if not data.strip():
            return None   # empty keepalive frame (``data:`` with no payload)
        return SseEvent(event, data)


def parse_sse_events(text: str) -> list[SseEvent]:
    """Parse a complete SSE document into its dispatched events, in order."""
    parser = SSEParser()
    events: list[SseEvent] = []
    for line in text.splitlines():
        if (event := parser.feed_line(line)) is not None:
            events.append(event)
    if (event := parser.flush()) is not None:
        events.append(event)
    return events
