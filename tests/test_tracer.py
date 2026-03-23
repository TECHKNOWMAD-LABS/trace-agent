"""Tests for the core Tracer."""
import pytest

from traceagent.models import SpanStatus
from traceagent.storage import InMemoryStorage
from traceagent.tracer import Tracer, get_tracer, set_global_tracer


def fresh_tracer() -> Tracer:
    return Tracer(storage=InMemoryStorage())


def test_span_context_manager():
    tracer = fresh_tracer()
    with tracer.start_span("root") as span:
        assert span.name == "root"
    assert span.end_time is not None
    assert span.status == SpanStatus.OK


def test_nested_spans_share_trace_id():
    tracer = fresh_tracer()
    with tracer.start_span("parent") as parent:
        with tracer.start_span("child") as child:
            assert child.trace_id == parent.trace_id
            assert child.parent_id == parent.span_id


def test_span_captures_exception():
    tracer = fresh_tracer()
    with pytest.raises(ValueError):
        with tracer.start_span("op") as span:
            raise ValueError("boom")
    assert span.status == SpanStatus.ERROR
    assert "boom" in span.error


def test_span_stored_after_context():
    tracer = fresh_tracer()
    with tracer.start_span("stored") as span:
        pass
    trace = tracer.get_storage().get_trace(span.trace_id)
    assert trace is not None
    assert trace.spans[0].name == "stored"


def test_get_active_span():
    tracer = fresh_tracer()
    assert tracer.get_active_span() is None
    with tracer.start_span("active") as span:
        assert tracer.get_active_span() is span
    assert tracer.get_active_span() is None


def test_get_tracer_creates_global_when_none():
    """get_tracer() creates a new global tracer when none exists (line 62)."""
    set_global_tracer(None)  # type: ignore[arg-type]
    t = get_tracer("fresh")
    assert t is not None
    assert isinstance(t, Tracer)


def test_get_tracer_returns_existing_global():
    """get_tracer() returns cached global tracer on subsequent calls."""
    t1 = get_tracer()
    t2 = get_tracer()
    assert t1 is t2
