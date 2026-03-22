"""Core Tracer implementation."""
from __future__ import annotations

import contextlib
import threading
from collections.abc import Generator
from contextvars import ContextVar
from typing import Any

from .models import Span, SpanStatus
from .storage import BaseStorage, InMemoryStorage

_active_span: ContextVar[Span | None] = ContextVar("_active_span", default=None)
_global_tracer: Tracer | None = None
_tracer_lock = threading.Lock()


class Tracer:
    def __init__(self, name: str = "default", storage: BaseStorage | None = None) -> None:
        self.name = name
        self.storage: BaseStorage = storage or InMemoryStorage()

    @contextlib.contextmanager
    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        parent: Span | None = None,
    ) -> Generator[Span, None, None]:
        parent_span = parent or _active_span.get()
        span = Span(name=name)
        if parent_span is not None:
            span.trace_id = parent_span.trace_id
            span.parent_id = parent_span.span_id
        if attributes:
            span.attributes.update(attributes)

        token = _active_span.set(span)
        try:
            yield span
        except Exception as exc:
            span.end(status=SpanStatus.ERROR, error=str(exc))
            raise
        else:
            if span.end_time is None:
                span.end()
        finally:
            _active_span.reset(token)
            self.storage.save_span(span)

    def get_active_span(self) -> Span | None:
        return _active_span.get()

    def get_storage(self) -> BaseStorage:
        return self.storage


def get_tracer(name: str = "default", storage: BaseStorage | None = None) -> Tracer:
    global _global_tracer
    with _tracer_lock:
        if _global_tracer is None:
            _global_tracer = Tracer(name=name, storage=storage or InMemoryStorage())
    return _global_tracer


def set_global_tracer(tracer: Tracer) -> None:
    global _global_tracer
    with _tracer_lock:
        _global_tracer = tracer
