"""Example 1 — Basic tracing with nested spans.

Demonstrates the core TraceAgent API: creating a Tracer, recording nested
spans, attaching attributes and events, and retrieving the stored trace.

Run:
    python examples/basic_tracing.py
"""
from __future__ import annotations

import sys
import time

sys.path.insert(0, "src")  # allow running from repo root without installing

from traceagent import Tracer, InMemoryStorage
from traceagent.models import SpanStatus


def simulate_http_request(tracer: Tracer, path: str) -> None:
    """Simulate a simple HTTP request with a database sub-call."""
    with tracer.start_span("http.request", attributes={"http.path": path, "http.method": "GET"}) as root:
        root.set_attribute("user.id", "u-42")

        # Simulate some processing time
        time.sleep(0.01)
        root.add_event("request.received", {"parser": "json"})

        # Nested span for the database call
        with tracer.start_span("db.query", attributes={"db.table": "users"}) as db_span:
            time.sleep(0.005)
            db_span.add_event("cache.miss")
            db_span.set_attribute("db.rows_returned", 1)

        root.add_event("response.sent", {"status_code": 200})


def simulate_error_path(tracer: Tracer) -> None:
    """Demonstrate how exceptions are automatically captured."""
    try:
        with tracer.start_span("risky.operation") as _span:
            raise ValueError("downstream service timeout")
    except ValueError:
        pass  # span is marked ERROR automatically


def main() -> None:
    storage = InMemoryStorage()
    tracer = Tracer(name="example-service", storage=storage)

    # Record two traces
    simulate_http_request(tracer, "/api/users/42")
    simulate_error_path(tracer)

    # Inspect the stored traces
    traces = storage.list_traces()
    print(f"\nRecorded {len(traces)} traces:\n")

    for trace in traces:
        print(f"  Trace {trace.trace_id[:12]}…  spans={len(trace.spans)}  "
              f"duration={trace.total_duration_ms:.1f}ms")
        for span in trace.spans:
            indent = "    " if span.parent_id else "  "
            status_icon = "✓" if span.status == SpanStatus.OK else "✗"
            print(f"{indent}{status_icon} {span.name:<30} {span.duration_ms or 0:.1f}ms")

    print("\nDone — all spans persisted in memory.")


if __name__ == "__main__":
    main()
