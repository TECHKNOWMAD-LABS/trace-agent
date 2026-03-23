"""Property-based tests using Hypothesis for TraceAgent core invariants."""
from __future__ import annotations

import json
import re

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from traceagent.models import Span, SpanStatus, Trace
from traceagent.mcp_server import MCPServer, _coerce_limit
from traceagent.storage import InMemoryStorage, _validate_limit, _validate_trace_id
from traceagent.tracer import Tracer

# ── Strategies ────────────────────────────────────────────────────────────────

valid_names = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00"),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip())  # non-empty after stripping

valid_attr_keys = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

valid_attr_values = st.one_of(
    st.text(max_size=200),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.booleans(),
    st.none(),
)

valid_trace_ids = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=64,
).filter(lambda s: s.strip())

# ── Span invariants ───────────────────────────────────────────────────────────

@given(name=valid_names)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_span_name_always_non_empty_after_construction(name: str) -> None:
    """Invariant: Span.name is always non-empty after construction."""
    span = Span(name=name)
    assert span.name.strip() != ""
    assert len(span.name) <= 512


@given(name=valid_names)
def test_span_duration_ms_none_before_end(name: str) -> None:
    """Invariant: duration_ms is None until end() is called."""
    span = Span(name=name)
    assert span.duration_ms is None


@given(name=valid_names)
def test_span_duration_ms_non_negative_after_end(name: str) -> None:
    """Invariant: duration_ms >= 0 after end()."""
    span = Span(name=name)
    span.end()
    assert span.duration_ms is not None
    assert span.duration_ms >= 0.0


@given(name=valid_names, error=st.text(max_size=1000))
def test_span_end_with_error_always_sets_error_status(name: str, error: str) -> None:
    """Invariant: passing non-empty error to end() always forces ERROR status."""
    assume(error)  # skip empty strings (they are falsy, don't trigger ERROR)
    span = Span(name=name)
    span.end(error=error)
    assert span.status == SpanStatus.ERROR


@given(name=valid_names)
def test_span_end_ok_sets_ok_status(name: str) -> None:
    """Invariant: end() with no error always sets OK status."""
    span = Span(name=name)
    span.end()
    assert span.status == SpanStatus.OK


@given(name=valid_names, key=valid_attr_keys, value=valid_attr_values)
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_span_set_attribute_round_trip(name: str, key: str, value: object) -> None:
    """Invariant: set_attribute stores the value (possibly truncated) and retrieves it."""
    span = Span(name=name)
    span.set_attribute(key, value)
    # Key should be present
    stored_key = key.strip()[:256]
    assert stored_key in span.attributes


@given(name=valid_names, event_name=valid_names)
def test_span_add_event_increases_count(name: str, event_name: str) -> None:
    """Invariant: add_event always increases events list length by 1."""
    span = Span(name=name)
    before = len(span.events)
    span.add_event(event_name)
    assert len(span.events) == before + 1


@given(name=valid_names)
def test_span_to_dict_serialisation_round_trip(name: str) -> None:
    """Invariant: Span.to_dict() produces a JSON-serialisable dict."""
    span = Span(name=name)
    span.end()
    d = span.to_dict()
    serialised = json.dumps(d)  # must not raise
    loaded = json.loads(serialised)
    assert loaded["name"] == span.name
    assert loaded["status"] == span.status.value


# ── Trace invariants ──────────────────────────────────────────────────────────

@given(names=st.lists(valid_names, min_size=1, max_size=10))
def test_trace_span_count_matches_added(names: list[str]) -> None:
    """Invariant: trace.span_count == len(spans added)."""
    trace = Trace(trace_id="t")
    for name in names:
        span = Span(name=name, trace_id="t")
        trace.add_span(span)
    d = trace.to_dict()
    assert d["span_count"] == len(names)


@given(names=st.lists(valid_names, min_size=1, max_size=5))
def test_trace_to_dict_round_trip(names: list[str]) -> None:
    """Invariant: Trace.to_dict() is JSON-serialisable."""
    trace = Trace(trace_id="prop-trace")
    for name in names:
        s = Span(name=name, trace_id="prop-trace")
        s.end()
        trace.add_span(s)
    d = trace.to_dict()
    json.dumps(d)  # must not raise


# ── Storage invariants ────────────────────────────────────────────────────────

@given(names=st.lists(valid_names, min_size=1, max_size=20))
@settings(max_examples=100)
def test_inmemory_save_retrieve_identity(names: list[str]) -> None:
    """Invariant: every saved span is retrievable by its trace_id."""
    store = InMemoryStorage()
    tracer = Tracer(storage=store)
    for name in names:
        with tracer.start_span(name) as span:
            pass
        trace = store.get_trace(span.trace_id)
        assert trace is not None
        assert any(s.name == span.name for s in trace.spans)


@given(limit=st.integers(min_value=0, max_value=10_000))
def test_inmemory_list_traces_respects_limit(limit: int) -> None:
    """Invariant: list_traces returns at most *limit* traces."""
    store = InMemoryStorage()
    for i in range(15):
        s = Span(name=f"op-{i}")
        s.end()
        store.save_span(s)
    results = store.list_traces(limit=limit)
    assert len(results) <= limit


# ── _validate_limit invariants ────────────────────────────────────────────────

@given(limit=st.integers())
def test_validate_limit_always_in_range(limit: int) -> None:
    """Invariant: _validate_limit always returns a value in [0, 10_000]."""
    result = _validate_limit(limit)
    assert 0 <= result <= 10_000


# ── _coerce_limit invariants ──────────────────────────────────────────────────

@given(value=st.one_of(st.integers(), st.floats(allow_nan=True), st.text(), st.none()))
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_coerce_limit_never_raises(value: object) -> None:
    """Invariant: _coerce_limit never raises — always returns an int."""
    result = _coerce_limit(value)
    assert isinstance(result, int)
    assert 0 <= result <= 1000


# ── MCPServer output invariants ───────────────────────────────────────────────

@given(tool_name=st.text(max_size=50))
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_mcp_call_tool_always_returns_valid_json(tool_name: str) -> None:
    """Invariant: call_tool always returns valid JSON regardless of tool_name."""
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    result = server.call_tool(tool_name)
    parsed = json.loads(result)  # must not raise
    assert isinstance(parsed, dict)


@given(limit=st.one_of(st.integers(), st.text(max_size=10), st.none()))
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_mcp_list_traces_always_returns_valid_json(limit: object) -> None:
    """Invariant: list_traces returns valid JSON for any limit value."""
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    result = server.call_tool("list_traces", {"limit": limit})
    parsed = json.loads(result)
    assert isinstance(parsed, dict)


@given(trace_id=st.one_of(st.text(max_size=50), st.none(), st.integers()))
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_mcp_get_trace_always_returns_valid_json(trace_id: object) -> None:
    """Invariant: get_trace returns valid JSON for any trace_id value."""
    server = MCPServer(tracer=Tracer(storage=InMemoryStorage()))
    result = server.call_tool("get_trace", {"trace_id": trace_id})
    parsed = json.loads(result)
    assert isinstance(parsed, dict)
