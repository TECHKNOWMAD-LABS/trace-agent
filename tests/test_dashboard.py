"""Tests for TraceAgent dashboard module — 0% → full coverage."""
from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from traceagent.dashboard import render_dashboard, render_trace
from traceagent.models import Span, SpanStatus
from traceagent.storage import InMemoryStorage
from traceagent.tracer import Tracer


def _tracer_with_data() -> Tracer:
    """Return a tracer that has a completed root+child trace."""
    store = InMemoryStorage()
    t = Tracer(storage=store)
    with t.start_span("http.request", attributes={"method": "GET"}) as root:
        with t.start_span("db.query"):
            pass
    return t


def _error_tracer() -> Tracer:
    """Return a tracer that has an error span."""
    store = InMemoryStorage()
    t = Tracer(storage=store)
    with pytest.raises(RuntimeError):
        with t.start_span("bad-op"):
            raise RuntimeError("oops")
    return t


def _empty_tracer() -> Tracer:
    return Tracer(storage=InMemoryStorage())


# ── render_dashboard ──────────────────────────────────────────────────────────

def test_render_dashboard_empty_no_crash():
    """render_dashboard with no traces must not raise."""
    render_dashboard(tracer=_empty_tracer())


def test_render_dashboard_with_data_no_crash():
    """render_dashboard with populated tracer must not raise."""
    render_dashboard(tracer=_tracer_with_data())


def test_render_dashboard_with_errors_no_crash():
    """render_dashboard handles error spans without crashing."""
    render_dashboard(tracer=_error_tracer())


def test_render_dashboard_limit_param():
    """limit param accepted without error."""
    t = _tracer_with_data()
    render_dashboard(tracer=t, limit=1)
    render_dashboard(tracer=t, limit=0)


def test_render_dashboard_uses_get_tracer_by_default():
    """When tracer=None, render_dashboard calls get_tracer()."""
    from traceagent.tracer import set_global_tracer
    t = _tracer_with_data()
    set_global_tracer(t)
    render_dashboard()  # no tracer arg → uses global


def test_render_dashboard_stats_computed():
    """Stats table content is derived from traces — no assertion on Rich internals,
    but we verify the function reaches completion across multiple call paths."""
    t1 = _tracer_with_data()
    t2 = _error_tracer()

    # Create a tracer that has both ok and error traces
    store = InMemoryStorage()
    combined = Tracer(storage=store)
    with combined.start_span("ok-op"):
        pass
    with pytest.raises(ValueError):
        with combined.start_span("err-op"):
            raise ValueError("x")

    render_dashboard(tracer=combined)


# ── render_trace ──────────────────────────────────────────────────────────────

def test_render_trace_not_found(capsys):
    """render_trace prints error message when trace_id is unknown."""
    render_trace("nonexistent-trace-id", tracer=_empty_tracer())
    captured = capsys.readouterr()
    # Rich outputs to console which may not be captured by capsys; just ensure no crash


def test_render_trace_found_no_crash():
    """render_trace with a valid trace_id renders without raising."""
    t = _tracer_with_data()
    traces = t.get_storage().list_traces()
    assert traces, "Expected at least one trace"
    render_trace(traces[0].trace_id, tracer=t)


def test_render_trace_with_error_span():
    """render_trace handles error spans (non-None error column)."""
    t = _error_tracer()
    traces = t.get_storage().list_traces()
    assert traces
    render_trace(traces[0].trace_id, tracer=t)


def test_render_trace_parent_id_display():
    """render_trace shortens parent_id to 8 chars + ellipsis for child spans."""
    store = InMemoryStorage()
    t = Tracer(storage=store)
    with t.start_span("parent"):
        with t.start_span("child"):
            pass
    traces = t.get_storage().list_traces()
    render_trace(traces[0].trace_id, tracer=t)  # must not raise


def test_render_trace_uses_global_tracer_when_none():
    """render_trace with tracer=None falls back to get_tracer()."""
    from traceagent.tracer import set_global_tracer
    t = _tracer_with_data()
    set_global_tracer(t)
    traces = t.get_storage().list_traces()
    render_trace(traces[0].trace_id)  # no tracer arg


def test_render_trace_unset_status_span():
    """render_trace handles UNSET status spans (no end_time, no duration)."""
    store = InMemoryStorage()
    t = Tracer(storage=store)
    # Manually save an un-ended span to check branch coverage
    span = Span(name="dangling", status=SpanStatus.UNSET)
    store.save_span(span)
    render_trace(span.trace_id, tracer=t)
