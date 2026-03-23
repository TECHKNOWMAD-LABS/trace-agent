"""MCP server exposing TraceAgent observability data."""
from __future__ import annotations

import json
import logging
from typing import Any

from .tracer import Tracer, get_tracer

logger = logging.getLogger(__name__)

_DEFAULT_LIST_LIMIT = 20
_MAX_LIST_LIMIT = 1000


def _coerce_limit(value: Any, default: int = _DEFAULT_LIST_LIMIT) -> int:
    """Safely coerce *value* to a positive integer limit.

    Returns *default* if *value* is None, non-numeric, or negative.
    Caps at _MAX_LIST_LIMIT to prevent run-away queries.
    """
    if value is None:
        return default
    try:
        limit = int(value)
    except (ValueError, TypeError):
        logger.warning("Invalid limit %r; using default %d", value, default)
        return default
    if limit < 0:
        logger.warning("Negative limit %d; using default %d", limit, default)
        return default
    return min(limit, _MAX_LIST_LIMIT)


def _handle_list_traces(tracer: Tracer, limit: int = _DEFAULT_LIST_LIMIT) -> dict[str, Any]:
    """Return a summary list of recent traces.

    Args:
        tracer: The Tracer whose storage is queried.
        limit: Maximum number of traces to include (clamped to [0, 1000]).

    Returns:
        Dictionary with ``traces`` list and ``total`` count.
    """
    limit = _coerce_limit(limit)
    traces = tracer.get_storage().list_traces(limit=limit)
    return {
        "traces": [
            {
                "trace_id": t.trace_id,
                "span_count": len(t.spans),
                "total_duration_ms": t.total_duration_ms,
                "root_span": t.root_span.name if t.root_span else None,
            }
            for t in traces
        ],
        "total": len(traces),
    }


def _handle_get_trace(tracer: Tracer, trace_id: str) -> dict[str, Any]:
    """Retrieve a single trace by its ID.

    Args:
        tracer: The Tracer whose storage is queried.
        trace_id: The trace identifier to look up.

    Returns:
        Serialised trace dict, or an ``{"error": ...}`` dict if not found.
    """
    if not trace_id or not isinstance(trace_id, str):
        return {"error": "trace_id must be a non-empty string"}
    trace = tracer.get_storage().get_trace(trace_id)
    if trace is None:
        return {"error": f"Trace {trace_id!r} not found"}
    return trace.to_dict()


def _handle_get_stats(tracer: Tracer) -> dict[str, Any]:
    """Return aggregated statistics across all stored traces.

    Args:
        tracer: The Tracer whose storage is queried.

    Returns:
        Dictionary with ``trace_count``, ``error_count``, and ``avg_duration_ms``.
    """
    traces = tracer.get_storage().list_traces(limit=_MAX_LIST_LIMIT)
    error_count = sum(
        1
        for t in traces
        for s in t.spans
        if s.status.value == "error"
    )
    durations = [t.total_duration_ms for t in traces if t.total_duration_ms is not None]
    avg_ms = sum(durations) / len(durations) if durations else 0.0
    return {
        "trace_count": len(traces),
        "error_count": error_count,
        "avg_duration_ms": round(avg_ms, 2),
    }


class MCPServer:
    """Minimal MCP-style server exposing TraceAgent observability data.

    Provides three tools: ``list_traces``, ``get_trace``, and ``get_stats``.
    All tool inputs are validated; unknown tools return an error dict rather than raising.

    Args:
        tracer: Optional Tracer instance. Uses the global tracer when omitted.
    """

    TOOLS = [
        {
            "name": "list_traces",
            "description": "List recent traces",
            "inputSchema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": _DEFAULT_LIST_LIMIT}},
            },
        },
        {
            "name": "get_trace",
            "description": "Get a specific trace by ID",
            "inputSchema": {
                "type": "object",
                "properties": {"trace_id": {"type": "string"}},
                "required": ["trace_id"],
            },
        },
        {
            "name": "get_stats",
            "description": "Get aggregated trace statistics",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]

    def __init__(self, tracer: Tracer | None = None) -> None:
        self._tracer = tracer or get_tracer()

    def list_tools(self) -> list[dict[str, Any]]:
        """Return the list of available tool definitions."""
        return self.TOOLS

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Dispatch a tool call by name.

        Args:
            name: Tool name to invoke.
            arguments: Optional dict of arguments passed to the tool.

        Returns:
            JSON-encoded result string. Always returns a valid JSON string —
            errors are returned as ``{"error": "..."}`` rather than raising.
        """
        if not isinstance(name, str) or not name.strip():
            return json.dumps({"error": "Tool name must be a non-empty string"}, indent=2)

        args = arguments or {}
        try:
            if name == "list_traces":
                result = _handle_list_traces(self._tracer, limit=args.get("limit", _DEFAULT_LIST_LIMIT))
            elif name == "get_trace":
                result = _handle_get_trace(self._tracer, trace_id=args.get("trace_id", ""))
            elif name == "get_stats":
                result = _handle_get_stats(self._tracer)
            else:
                result = {"error": f"Unknown tool: {name!r}"}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled error in tool %r", name)
            result = {"error": f"Internal error: {exc}"}
        return json.dumps(result, indent=2)
