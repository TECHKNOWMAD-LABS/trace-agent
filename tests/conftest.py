"""Shared fixtures and mock helpers for TraceAgent test suite."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from traceagent.models import Span, SpanStatus, Trace
from traceagent.storage import FileStorage, InMemoryStorage
from traceagent.tracer import Tracer, set_global_tracer


@pytest.fixture
def memory_storage() -> InMemoryStorage:
    """Fresh in-memory storage backend."""
    return InMemoryStorage()


@pytest.fixture
def tracer(memory_storage: InMemoryStorage) -> Tracer:
    """Fresh tracer backed by in-memory storage."""
    t = Tracer(name="test-tracer", storage=memory_storage)
    set_global_tracer(t)
    return t


@pytest.fixture
def tmp_dir() -> Generator[Path, None, None]:
    """Temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def file_storage(tmp_dir: Path) -> FileStorage:
    """Fresh file-backed storage backend."""
    return FileStorage(tmp_dir)


def make_span(
    name: str = "op",
    *,
    status: SpanStatus = SpanStatus.OK,
    error: str | None = None,
    trace_id: str | None = None,
    parent_id: str | None = None,
) -> Span:
    """Build and end a span with sensible defaults."""
    kwargs = {}
    if trace_id:
        kwargs["trace_id"] = trace_id
    if parent_id:
        kwargs["parent_id"] = parent_id
    s = Span(name=name, **kwargs)
    s.end(status=status, error=error)
    return s


def make_trace_with_spans(tracer: Tracer, n_children: int = 2) -> tuple[str, list[str]]:
    """Record a root span with *n_children* child spans, return (trace_id, span_names)."""
    span_names = ["root"] + [f"child-{i}" for i in range(n_children)]
    with tracer.start_span("root") as root:
        for i in range(n_children):
            with tracer.start_span(f"child-{i}"):
                pass
    return root.trace_id, span_names
