"""Tests for TraceAgent models."""
import time

from traceagent.models import Span, SpanStatus, Trace


def test_span_defaults():
    span = Span(name="test-op")
    assert span.name == "test-op"
    assert span.status == SpanStatus.UNSET
    assert span.end_time is None
    assert span.duration_ms is None
    assert span.parent_id is None


def test_span_end_ok():
    span = Span(name="op")
    time.sleep(0.01)
    span.end()
    assert span.status == SpanStatus.OK
    assert span.end_time is not None
    assert span.duration_ms is not None
    assert span.duration_ms >= 0


def test_span_end_error():
    span = Span(name="op")
    span.end(error="something failed")
    assert span.status == SpanStatus.ERROR
    assert span.error == "something failed"


def test_span_add_event():
    span = Span(name="op")
    span.add_event("cache_miss", {"key": "foo"})
    assert len(span.events) == 1
    assert span.events[0]["name"] == "cache_miss"


def test_span_set_attribute():
    span = Span(name="op")
    span.set_attribute("http.method", "GET")
    assert span.attributes["http.method"] == "GET"


def test_span_to_dict():
    span = Span(name="op")
    span.end()
    d = span.to_dict()
    assert d["name"] == "op"
    assert "duration_ms" in d
    assert d["status"] == "ok"


def test_trace_root_span():
    trace = Trace(trace_id="abc")
    root = Span(name="root")
    child = Span(name="child", trace_id="abc", parent_id=root.span_id)
    trace.add_span(root)
    trace.add_span(child)
    assert trace.root_span is root


def test_trace_to_dict():
    trace = Trace(trace_id="xyz")
    span = Span(name="op", trace_id="xyz")
    span.end()
    trace.add_span(span)
    d = trace.to_dict()
    assert d["trace_id"] == "xyz"
    assert d["span_count"] == 1
