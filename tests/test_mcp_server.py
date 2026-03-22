"""Tests for MCPServer."""
import json

from traceagent.mcp_server import MCPServer
from traceagent.storage import InMemoryStorage
from traceagent.tracer import Tracer


def make_tracer_with_spans() -> Tracer:
    store = InMemoryStorage()
    tracer = Tracer(storage=store)
    with tracer.start_span("root"):
        with tracer.start_span("child"):
            pass
    return tracer


def test_list_tools():
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    tools = server.list_tools()
    names = [t["name"] for t in tools]
    assert "list_traces" in names
    assert "get_trace" in names
    assert "get_stats" in names


def test_list_traces_empty():
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    result = json.loads(server.call_tool("list_traces"))
    assert result["total"] == 0


def test_list_traces_with_data():
    tracer = make_tracer_with_spans()
    server = MCPServer(tracer=tracer)
    result = json.loads(server.call_tool("list_traces"))
    assert result["total"] >= 1


def test_get_trace_found():
    tracer = make_tracer_with_spans()
    server = MCPServer(tracer=tracer)
    traces = json.loads(server.call_tool("list_traces"))["traces"]
    tid = traces[0]["trace_id"]
    trace_data = json.loads(server.call_tool("get_trace", {"trace_id": tid}))
    assert trace_data["trace_id"] == tid


def test_get_trace_not_found():
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    result = json.loads(server.call_tool("get_trace", {"trace_id": "nope"}))
    assert "error" in result


def test_get_stats():
    tracer = make_tracer_with_spans()
    server = MCPServer(tracer=tracer)
    stats = json.loads(server.call_tool("get_stats"))
    assert "trace_count" in stats
    assert stats["trace_count"] >= 1


def test_unknown_tool():
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    result = json.loads(server.call_tool("nonexistent"))
    assert "error" in result
