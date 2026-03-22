"""MCP server exposing TraceAgent observability data."""
from __future__ import annotations

import json
from typing import Any

from .tracer import Tracer, get_tracer


def _handle_list_traces(tracer: Tracer, limit: int = 20) -> dict[str, Any]:
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
    trace = tracer.get_storage().get_trace(trace_id)
    if trace is None:
        return {"error": f"Trace {trace_id!r} not found"}
    return trace.to_dict()


def _handle_get_stats(tracer: Tracer) -> dict[str, Any]:
    traces = tracer.get_storage().list_traces(limit=1000)
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
    """Minimal MCP-style server for TraceAgent."""

    TOOLS = [
        {
            "name": "list_traces",
            "description": "List recent traces",
            "inputSchema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 20}},
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
        return self.TOOLS

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        args = arguments or {}
        if name == "list_traces":
            result = _handle_list_traces(self._tracer, limit=args.get("limit", 20))
        elif name == "get_trace":
            result = _handle_get_trace(self._tracer, trace_id=args["trace_id"])
        elif name == "get_stats":
            result = _handle_get_stats(self._tracer)
        else:
            result = {"error": f"Unknown tool: {name!r}"}
        return json.dumps(result, indent=2)
