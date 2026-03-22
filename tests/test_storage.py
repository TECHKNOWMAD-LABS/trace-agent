"""Tests for TraceAgent storage backends."""
import tempfile
from pathlib import Path

from traceagent.models import Span
from traceagent.storage import FileStorage, InMemoryStorage


def make_span(name: str = "op") -> Span:
    s = Span(name=name)
    s.end()
    return s


def test_inmemory_save_and_retrieve():
    store = InMemoryStorage()
    span = make_span()
    store.save_span(span)
    trace = store.get_trace(span.trace_id)
    assert trace is not None
    assert len(trace.spans) == 1
    assert trace.spans[0].name == "op"


def test_inmemory_list_traces():
    store = InMemoryStorage()
    for i in range(5):
        store.save_span(make_span(f"op-{i}"))
    traces = store.list_traces(limit=10)
    assert len(traces) == 5


def test_inmemory_clear():
    store = InMemoryStorage()
    store.save_span(make_span())
    store.clear()
    assert store.span_count == 0


def test_inmemory_missing_trace():
    store = InMemoryStorage()
    assert store.get_trace("nonexistent") is None


def test_file_storage_save_retrieve():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStorage(tmpdir)
        span = make_span("db-query")
        store.save_span(span)
        trace = store.get_trace(span.trace_id)
        assert trace is not None
        assert trace.spans[0].name == "db-query"


def test_file_storage_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStorage(tmpdir)
        for _ in range(3):
            store.save_span(make_span())
        traces = store.list_traces()
        assert len(traces) == 3


def test_file_storage_clear():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = FileStorage(tmpdir)
        store.save_span(make_span())
        store.clear()
        assert len(list(Path(tmpdir).glob("*.json"))) == 0
