"""Data models for TraceAgent."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

_MAX_NAME_LEN = 512
_MAX_ATTR_KEY_LEN = 256
_MAX_ATTR_VALUE_STR_LEN = 4096
_MAX_ERROR_LEN = 8192
_MAX_EVENT_NAME_LEN = 256


def _validate_name(name: str, label: str = "name") -> str:
    """Validate and normalise a span/event name string.

    Raises ValueError for None, non-string, or empty after stripping.
    Truncates silently if longer than _MAX_NAME_LEN.
    """
    if name is None:
        raise ValueError(f"Span {label} must not be None")
    if not isinstance(name, str):
        raise TypeError(f"Span {label} must be a str, got {type(name).__name__!r}")
    name = name.strip()
    if not name:
        raise ValueError(f"Span {label} must not be empty")
    return name[:_MAX_NAME_LEN]


class SpanStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


@dataclass
class Span:
    """Represents a single unit of work within a distributed trace.

    Attributes:
        name: Human-readable operation name (required, non-empty).
        trace_id: Unique identifier shared across all spans in a trace.
        span_id: Unique identifier for this span.
        parent_id: span_id of the parent span, or None for root spans.
        start_time: Unix timestamp (seconds) when the span started.
        end_time: Unix timestamp (seconds) when the span ended, or None.
        status: Current status of the span (OK, ERROR, UNSET).
        attributes: Key-value metadata attached to this span.
        events: Timestamped events recorded within the span lifetime.
        error: Human-readable error message if status is ERROR.
    """

    name: str
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    parent_id: str | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    status: SpanStatus = SpanStatus.UNSET
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def __post_init__(self) -> None:
        self.name = _validate_name(self.name)

    @property
    def duration_ms(self) -> float | None:
        """Return elapsed milliseconds, or None if the span has not ended."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def end(self, status: SpanStatus = SpanStatus.OK, error: str | None = None) -> None:
        """Mark the span as ended.

        Args:
            status: Terminal status to assign (defaults to OK).
            error: Optional error message; forces status to ERROR when provided.
        """
        self.end_time = time.time()
        self.status = status
        if error:
            # Truncate to avoid unbounded memory usage from huge exception messages
            self.error = str(error)[:_MAX_ERROR_LEN]
            self.status = SpanStatus.ERROR

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Record a timestamped event within this span.

        Args:
            name: Non-empty event name (truncated to 256 chars).
            attributes: Optional key-value pairs attached to the event.

        Raises:
            ValueError: If *name* is empty or None.
            TypeError: If *name* is not a str.
        """
        name = _validate_name(name, label="event name")[:_MAX_EVENT_NAME_LEN]
        if attributes is not None and not isinstance(attributes, dict):
            raise TypeError(f"attributes must be a dict, got {type(attributes).__name__!r}")
        self.events.append({"name": name, "timestamp": time.time(), "attributes": attributes or {}})

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a metadata attribute on this span.

        Args:
            key: Non-empty attribute key (truncated to 256 chars).
            value: Attribute value (any JSON-serialisable type recommended).

        Raises:
            ValueError: If *key* is empty or None.
            TypeError: If *key* is not a str.
        """
        if key is None:
            raise ValueError("Attribute key must not be None")
        if not isinstance(key, str):
            raise TypeError(f"Attribute key must be a str, got {type(key).__name__!r}")
        key = key.strip()
        if not key:
            raise ValueError("Attribute key must not be empty")
        key = key[:_MAX_ATTR_KEY_LEN]
        # Truncate string values only; leave other types intact
        if isinstance(value, str):
            value = value[:_MAX_ATTR_VALUE_STR_LEN]
        self.attributes[key] = value

    def to_dict(self) -> dict[str, Any]:
        """Serialise this span to a plain dictionary."""
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "attributes": self.attributes,
            "events": self.events,
            "error": self.error,
        }


@dataclass
class Trace:
    """Collection of spans that share a common trace_id.

    Attributes:
        trace_id: Unique identifier for this trace.
        spans: Ordered list of spans belonging to this trace.
    """

    trace_id: str
    spans: list[Span] = field(default_factory=list)

    @property
    def root_span(self) -> Span | None:
        """Return the first span without a parent_id, or None."""
        return next((s for s in self.spans if s.parent_id is None), None)

    @property
    def total_duration_ms(self) -> float | None:
        """Return end-to-end duration in milliseconds from the root span, or None."""
        root = self.root_span
        if root is None:
            return None
        return root.duration_ms

    def add_span(self, span: Span) -> None:
        """Append *span* to this trace.

        Args:
            span: The span to add.

        Raises:
            TypeError: If *span* is not a Span instance.
        """
        if not isinstance(span, Span):
            raise TypeError(f"Expected a Span, got {type(span).__name__!r}")
        self.spans.append(span)

    def to_dict(self) -> dict[str, Any]:
        """Serialise this trace (including all spans) to a plain dictionary."""
        return {
            "trace_id": self.trace_id,
            "total_duration_ms": self.total_duration_ms,
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
        }
