"""Storage backends for TraceAgent."""
from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .models import Span, SpanStatus, Trace


class BaseStorage(ABC):
    @abstractmethod
    def save_span(self, span: Span) -> None: ...

    @abstractmethod
    def get_trace(self, trace_id: str) -> Trace | None: ...

    @abstractmethod
    def list_traces(self, limit: int = 100) -> list[Trace]: ...

    @abstractmethod
    def clear(self) -> None: ...


class InMemoryStorage(BaseStorage):
    def __init__(self) -> None:
        self._spans: dict[str, list[Span]] = {}  # trace_id -> spans
        self._lock = threading.Lock()

    def save_span(self, span: Span) -> None:
        with self._lock:
            self._spans.setdefault(span.trace_id, []).append(span)

    def get_trace(self, trace_id: str) -> Trace | None:
        with self._lock:
            spans = self._spans.get(trace_id)
            if spans is None:
                return None
            trace = Trace(trace_id=trace_id)
            trace.spans = list(spans)
            return trace

    def list_traces(self, limit: int = 100) -> list[Trace]:
        with self._lock:
            traces = []
            for tid, spans in list(self._spans.items())[-limit:]:
                trace = Trace(trace_id=tid, spans=list(spans))
                traces.append(trace)
            return traces

    def clear(self) -> None:
        with self._lock:
            self._spans.clear()

    @property
    def span_count(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._spans.values())


def _span_from_dict(data: dict[str, Any]) -> Span:
    span = Span(
        name=data["name"],
        trace_id=data["trace_id"],
        span_id=data["span_id"],
        parent_id=data.get("parent_id"),
        start_time=data["start_time"],
        end_time=data.get("end_time"),
        status=SpanStatus(data.get("status", "unset")),
        attributes=data.get("attributes", {}),
        events=data.get("events", []),
        error=data.get("error"),
    )
    return span


class FileStorage(BaseStorage):
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _trace_file(self, trace_id: str) -> Path:
        return self._path / f"{trace_id}.json"

    def save_span(self, span: Span) -> None:
        with self._lock:
            tf = self._trace_file(span.trace_id)
            if tf.exists():
                data = json.loads(tf.read_text())
            else:
                data = {"trace_id": span.trace_id, "spans": []}
            data["spans"].append(span.to_dict())
            tf.write_text(json.dumps(data, indent=2))

    def get_trace(self, trace_id: str) -> Trace | None:
        tf = self._trace_file(trace_id)
        if not tf.exists():
            return None
        data = json.loads(tf.read_text())
        trace = Trace(trace_id=trace_id)
        trace.spans = [_span_from_dict(s) for s in data.get("spans", [])]
        return trace

    def list_traces(self, limit: int = 100) -> list[Trace]:
        all_files = sorted(self._path.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        files = all_files[:limit]
        traces = []
        for f in files:
            data = json.loads(f.read_text())
            trace = Trace(trace_id=data["trace_id"])
            trace.spans = [_span_from_dict(s) for s in data.get("spans", [])]
            traces.append(trace)
        return traces

    def clear(self) -> None:
        with self._lock:
            for f in self._path.glob("*.json"):
                f.unlink()
