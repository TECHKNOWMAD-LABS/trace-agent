"""Error hardening tests — empty inputs, None, malformed data, huge strings, unicode."""
from __future__ import annotations

import json
import tempfile

import pytest

from traceagent.mcp_server import MCPServer, _coerce_limit
from traceagent.models import Span, SpanStatus, Trace
from traceagent.storage import FileStorage, InMemoryStorage, _validate_limit, _validate_trace_id
from traceagent.tracer import Tracer

# ── Span name validation ─────────────────────────────────────────────────────

def test_span_none_name_raises():
    with pytest.raises((ValueError, TypeError)):
        Span(name=None)  # type: ignore[arg-type]


def test_span_empty_name_raises():
    with pytest.raises(ValueError):
        Span(name="")


def test_span_whitespace_only_name_raises():
    with pytest.raises(ValueError):
        Span(name="   \t\n")


def test_span_non_string_name_raises():
    with pytest.raises(TypeError):
        Span(name=42)  # type: ignore[arg-type]


def test_span_huge_name_truncated():
    big = "x" * 10_000
    span = Span(name=big)
    assert len(span.name) <= 512


def test_span_unicode_name_ok():
    span = Span(name="操作 — ünïcödé ✓")
    assert "ünïcödé" in span.name


def test_span_name_leading_trailing_whitespace_stripped():
    span = Span(name="  hello world  ")
    assert span.name == "hello world"


# ── Span.add_event validation ────────────────────────────────────────────────

def test_add_event_none_name_raises():
    span = Span(name="op")
    with pytest.raises((ValueError, TypeError)):
        span.add_event(None)  # type: ignore[arg-type]


def test_add_event_empty_name_raises():
    span = Span(name="op")
    with pytest.raises(ValueError):
        span.add_event("")


def test_add_event_non_dict_attributes_raises():
    span = Span(name="op")
    with pytest.raises(TypeError):
        span.add_event("ev", attributes="not-a-dict")  # type: ignore[arg-type]


def test_add_event_none_attributes_ok():
    span = Span(name="op")
    span.add_event("ev", attributes=None)
    assert span.events[0]["attributes"] == {}


def test_add_event_huge_name_truncated():
    span = Span(name="op")
    span.add_event("x" * 5000)
    assert len(span.events[0]["name"]) <= 256


# ── Span.set_attribute validation ────────────────────────────────────────────

def test_set_attribute_none_key_raises():
    span = Span(name="op")
    with pytest.raises(ValueError):
        span.set_attribute(None, "v")  # type: ignore[arg-type]


def test_set_attribute_empty_key_raises():
    span = Span(name="op")
    with pytest.raises(ValueError):
        span.set_attribute("", "v")


def test_set_attribute_non_string_key_raises():
    span = Span(name="op")
    with pytest.raises(TypeError):
        span.set_attribute(123, "v")  # type: ignore[arg-type]


def test_set_attribute_huge_string_value_truncated():
    span = Span(name="op")
    span.set_attribute("key", "v" * 10_000)
    assert len(span.attributes["key"]) <= 4096


def test_set_attribute_non_string_value_preserved():
    span = Span(name="op")
    span.set_attribute("count", 42)
    assert span.attributes["count"] == 42


def test_set_attribute_unicode_key_and_value():
    span = Span(name="op")
    span.set_attribute("emoji_🔑", "value_🎉")
    assert span.attributes["emoji_🔑"] == "value_🎉"


def test_set_attribute_none_value_ok():
    span = Span(name="op")
    span.set_attribute("k", None)
    assert span.attributes["k"] is None


# ── Span.end with edge cases ─────────────────────────────────────────────────

def test_span_end_huge_error_truncated():
    span = Span(name="op")
    span.end(error="E" * 100_000)
    assert len(span.error) <= 8192


def test_span_end_empty_error_does_not_override_ok():
    span = Span(name="op")
    span.end(error="")
    # empty string is falsy — should not force ERROR status
    assert span.status == SpanStatus.OK


# ── Trace.add_span validation ─────────────────────────────────────────────────

def test_trace_add_span_non_span_raises():
    trace = Trace(trace_id="t1")
    with pytest.raises(TypeError):
        trace.add_span("not-a-span")  # type: ignore[arg-type]


def test_trace_add_span_none_raises():
    trace = Trace(trace_id="t1")
    with pytest.raises(TypeError):
        trace.add_span(None)  # type: ignore[arg-type]


# ── Storage validation helpers ───────────────────────────────────────────────

def test_validate_trace_id_none_raises():
    with pytest.raises(ValueError):
        _validate_trace_id(None)  # type: ignore[arg-type]


def test_validate_trace_id_empty_raises():
    with pytest.raises(ValueError):
        _validate_trace_id("")


def test_validate_trace_id_non_string_raises():
    with pytest.raises(TypeError):
        _validate_trace_id(123)  # type: ignore[arg-type]


def test_validate_trace_id_huge_truncated():
    long_id = "a" * 1000
    result = _validate_trace_id(long_id)
    assert len(result) <= 128


def test_validate_limit_non_int_raises():
    with pytest.raises(TypeError):
        _validate_limit("bad")  # type: ignore[arg-type]


def test_validate_limit_negative_clamped():
    assert _validate_limit(-10) == 0


def test_validate_limit_huge_clamped():
    assert _validate_limit(999_999) == 10_000


# ── InMemoryStorage error paths ───────────────────────────────────────────────

def test_inmemory_save_non_span_raises():
    store = InMemoryStorage()
    with pytest.raises(TypeError):
        store.save_span("not-a-span")  # type: ignore[arg-type]


def test_inmemory_get_trace_none_raises():
    store = InMemoryStorage()
    with pytest.raises(ValueError):
        store.get_trace(None)  # type: ignore[arg-type]


def test_inmemory_get_trace_empty_raises():
    store = InMemoryStorage()
    with pytest.raises(ValueError):
        store.get_trace("")


def test_inmemory_list_traces_bad_limit_raises():
    store = InMemoryStorage()
    with pytest.raises(TypeError):
        store.list_traces(limit="bad")  # type: ignore[arg-type]


# ── FileStorage error paths ───────────────────────────────────────────────────

def test_file_storage_none_path_raises():
    with pytest.raises(ValueError):
        FileStorage(None)  # type: ignore[arg-type]


def test_file_storage_save_non_span_raises():
    with tempfile.TemporaryDirectory() as d:
        store = FileStorage(d)
        with pytest.raises(TypeError):
            store.save_span("not-a-span")  # type: ignore[arg-type]


def test_file_storage_get_trace_empty_raises():
    with tempfile.TemporaryDirectory() as d:
        store = FileStorage(d)
        with pytest.raises(ValueError):
            store.get_trace("")


def test_file_storage_skips_corrupt_json(tmp_path):
    """list_traces logs a warning and skips files with invalid JSON."""
    store = FileStorage(tmp_path)
    # Write a legitimate span first
    span = Span(name="ok")
    span.end()
    store.save_span(span)
    # Corrupt a file in the directory
    (tmp_path / "corrupt.json").write_text("{invalid json}")
    # Should return 1 trace (not raise)
    traces = store.list_traces()
    assert len(traces) == 1


# ── MCPServer error paths ─────────────────────────────────────────────────────

def test_mcp_empty_tool_name():
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    result = json.loads(server.call_tool(""))
    assert "error" in result


def test_mcp_none_tool_name():
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    result = json.loads(server.call_tool(None))  # type: ignore[arg-type]
    assert "error" in result


def test_mcp_get_trace_empty_id():
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    result = json.loads(server.call_tool("get_trace", {"trace_id": ""}))
    assert "error" in result


def test_mcp_get_trace_missing_key():
    """get_trace with no trace_id in args returns error (not KeyError crash)."""
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    result = json.loads(server.call_tool("get_trace", {}))
    assert "error" in result


def test_mcp_list_traces_bad_limit():
    """list_traces with a string limit falls back to default gracefully."""
    tracer = Tracer(storage=InMemoryStorage())
    with tracer.start_span("x"):
        pass
    server = MCPServer(tracer=tracer)
    result = json.loads(server.call_tool("list_traces", {"limit": "bad"}))
    # Should succeed with fallback limit, returning traces list
    assert "traces" in result


def test_mcp_list_traces_negative_limit():
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    result = json.loads(server.call_tool("list_traces", {"limit": -1}))
    assert "traces" in result


def test_mcp_call_tool_none_arguments():
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    result = json.loads(server.call_tool("get_stats", None))
    assert "trace_count" in result


# ── Coerce limit helper ───────────────────────────────────────────────────────

def test_coerce_limit_none_returns_default():
    assert _coerce_limit(None) == 20


def test_coerce_limit_string_number():
    assert _coerce_limit("10") == 10


def test_coerce_limit_float_truncates():
    assert _coerce_limit(5.9) == 5


def test_coerce_limit_non_numeric_string():
    assert _coerce_limit("abc") == 20


def test_coerce_limit_negative():
    assert _coerce_limit(-5) == 20


def test_coerce_limit_huge_clamped():
    assert _coerce_limit(999_999) == 1000
