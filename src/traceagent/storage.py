"""Storage backends for TraceAgent."""
from __future__ import annotations

import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .models import Span, SpanStatus, Trace

logger = logging.getLogger(__name__)

_MAX_TRACE_ID_LEN = 128
_DEFAULT_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 0.05  # seconds


def _validate_trace_id(trace_id: str) -> str:
    """Validate and return a trace_id string.

    Raises:
        ValueError: If trace_id is None or empty after stripping.
        TypeError: If trace_id is not a str.
    """
    if trace_id is None:
        raise ValueError("trace_id must not be None")
    if not isinstance(trace_id, str):
        raise TypeError(f"trace_id must be a str, got {type(trace_id).__name__!r}")
    trace_id = trace_id.strip()
    if not trace_id:
        raise ValueError("trace_id must not be empty")
    return trace_id[:_MAX_TRACE_ID_LEN]


def _validate_limit(limit: int) -> int:
    """Clamp limit to [0, 10000].

    Raises:
        TypeError: If limit is not an int.
    """
    if not isinstance(limit, int):
        raise TypeError(f"limit must be an int, got {type(limit).__name__!r}")
    return max(0, min(limit, 10_000))


class BaseStorage(ABC):
    """Abstract base class for TraceAgent storage backends."""

    @abstractmethod
    def save_span(self, span: Span) -> None:
        """Persist *span* to the storage backend."""
        ...

    @abstractmethod
    def get_trace(self, trace_id: str) -> Trace | None:
        """Retrieve a trace by its ID, or return None if not found."""
        ...

    @abstractmethod
    def list_traces(self, limit: int = 100) -> list[Trace]:
        """Return the most recent *limit* traces."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Delete all stored spans/traces."""
        ...


class InMemoryStorage(BaseStorage):
    """Thread-safe in-memory storage backend.

    Suitable for testing and short-lived processes. Data is lost on restart.
    """

    def __init__(self) -> None:
        self._spans: dict[str, list[Span]] = {}  # trace_id -> spans
        self._lock = threading.Lock()

    def save_span(self, span: Span) -> None:
        """Save *span* in memory.

        Args:
            span: The span to persist.

        Raises:
            TypeError: If *span* is not a Span instance.
        """
        if not isinstance(span, Span):
            raise TypeError(f"Expected a Span, got {type(span).__name__!r}")
        with self._lock:
            self._spans.setdefault(span.trace_id, []).append(span)

    def get_trace(self, trace_id: str) -> Trace | None:
        """Retrieve a trace by ID.

        Args:
            trace_id: The trace identifier to look up.

        Returns:
            A Trace object, or None if no spans were recorded for that ID.
        """
        trace_id = _validate_trace_id(trace_id)
        with self._lock:
            spans = self._spans.get(trace_id)
            if spans is None:
                return None
            trace = Trace(trace_id=trace_id)
            trace.spans = list(spans)
            return trace

    def list_traces(self, limit: int = 100) -> list[Trace]:
        """Return up to *limit* traces in insertion order.

        Args:
            limit: Maximum number of traces to return (clamped to [0, 10000]).
        """
        limit = _validate_limit(limit)
        with self._lock:
            traces = []
            for tid, spans in list(self._spans.items())[-limit:]:
                trace = Trace(trace_id=tid, spans=list(spans))
                traces.append(trace)
            return traces

    def clear(self) -> None:
        """Remove all spans from memory."""
        with self._lock:
            self._spans.clear()

    @property
    def span_count(self) -> int:
        """Total number of spans currently stored."""
        with self._lock:
            return sum(len(v) for v in self._spans.values())


def _span_from_dict(data: dict[str, Any]) -> Span:
    """Reconstruct a Span from a serialised dictionary.

    Args:
        data: Dictionary produced by Span.to_dict().

    Returns:
        A Span with fields populated from *data*.

    Raises:
        KeyError: If required fields are missing.
        ValueError: If field values are invalid.
    """
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


def _retry(fn: Any, attempts: int = _DEFAULT_RETRY_ATTEMPTS, base_delay: float = _RETRY_BASE_DELAY) -> Any:
    """Execute *fn* with exponential back-off retry.

    Args:
        fn: Zero-argument callable to execute.
        attempts: Maximum number of attempts (default 3).
        base_delay: Initial sleep duration in seconds; doubles each retry.

    Raises:
        The last exception raised by *fn* after all attempts are exhausted.
    """
    last_exc: Exception | None = None
    delay = base_delay
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < attempts:
                logger.debug("Retry %d/%d after error: %s", attempt, attempts, exc)
                time.sleep(delay)
                delay *= 2
    raise last_exc  # type: ignore[misc]


class FileStorage(BaseStorage):
    """Thread-safe file-backed storage backend.

    Each trace is stored as a JSON file named ``{trace_id}.json`` in *path*.
    Writes use 3-attempt exponential back-off retry to handle transient I/O errors.

    Args:
        path: Directory where trace files are stored (created if absent).
    """

    def __init__(self, path: str | Path) -> None:
        if path is None:
            raise ValueError("FileStorage path must not be None")
        self._path = Path(path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _trace_file(self, trace_id: str) -> Path:
        return self._path / f"{trace_id}.json"

    def save_span(self, span: Span) -> None:
        """Persist *span* to disk with retry on transient failure.

        Args:
            span: The span to save.

        Raises:
            TypeError: If *span* is not a Span instance.
            OSError: If the write fails after all retry attempts.
        """
        if not isinstance(span, Span):
            raise TypeError(f"Expected a Span, got {type(span).__name__!r}")

        def _write() -> None:
            with self._lock:
                tf = self._trace_file(span.trace_id)
                if tf.exists():
                    data = json.loads(tf.read_text())
                else:
                    data = {"trace_id": span.trace_id, "spans": []}
                data["spans"].append(span.to_dict())
                tf.write_text(json.dumps(data, indent=2))

        _retry(_write)

    def get_trace(self, trace_id: str) -> Trace | None:
        """Read a trace from disk.

        Args:
            trace_id: Identifier of the trace to retrieve.

        Returns:
            A Trace object, or None if no file exists for *trace_id*.

        Raises:
            ValueError: If *trace_id* is empty or None.
        """
        trace_id = _validate_trace_id(trace_id)
        tf = self._trace_file(trace_id)
        if not tf.exists():
            return None
        data = json.loads(tf.read_text())
        trace = Trace(trace_id=trace_id)
        trace.spans = [_span_from_dict(s) for s in data.get("spans", [])]
        return trace

    def list_traces(self, limit: int = 100) -> list[Trace]:
        """Return up to *limit* traces sorted by modification time (newest first).

        Args:
            limit: Maximum number of traces to return.
        """
        limit = _validate_limit(limit)
        all_files = sorted(self._path.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        files = all_files[:limit]
        traces = []
        for f in files:
            try:
                data = json.loads(f.read_text())
                trace = Trace(trace_id=data["trace_id"])
                trace.spans = [_span_from_dict(s) for s in data.get("spans", [])]
                traces.append(trace)
            except (json.JSONDecodeError, KeyError, OSError) as exc:
                logger.warning("Skipping corrupt trace file %s: %s", f, exc)
        return traces

    def clear(self) -> None:
        """Delete all trace files from the storage directory."""
        with self._lock:
            for f in self._path.glob("*.json"):
                f.unlink()
