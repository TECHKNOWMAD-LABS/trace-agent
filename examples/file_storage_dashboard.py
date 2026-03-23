"""Example 3 — Persistent FileStorage and Rich dashboard.

Records traces to disk and renders them using the built-in Rich dashboard.
Demonstrates FileStorage persistence and the render_dashboard / render_trace
display functions.

Run:
    python examples/file_storage_dashboard.py
"""
from __future__ import annotations

import sys
import tempfile
import time

sys.path.insert(0, "src")  # allow running from repo root without installing

from traceagent import FileStorage, Tracer
from traceagent.dashboard import render_dashboard, render_trace
from traceagent.async_storage import CachedStorage


def populate_traces(tracer: Tracer, n: int = 8) -> list[str]:
    """Record *n* traces and return their IDs."""
    trace_ids = []
    for i in range(n):
        with tracer.start_span(f"job.{i}", attributes={"job.index": i}) as root:
            time.sleep(0.002)
            with tracer.start_span("db.read"):
                time.sleep(0.001)
            if i % 3 == 0:
                with tracer.start_span("cache.write"):
                    pass
        trace_ids.append(root.trace_id)

    # Record one error trace
    try:
        with tracer.start_span("broken.job"):
            raise RuntimeError("simulated failure")
    except RuntimeError:
        pass

    return trace_ids


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Use FileStorage with CachedStorage wrapper
        file_store = FileStorage(tmpdir)
        cached = CachedStorage(file_store, maxsize=64)
        tracer = Tracer(name="file-example", storage=cached)  # type: ignore[arg-type]

        print("Recording traces to disk …")
        trace_ids = populate_traces(tracer)

        print(f"\nRecorded {len(trace_ids) + 1} traces to: {tmpdir}\n")

        # Render the summary dashboard
        render_dashboard(tracer=tracer, limit=20)

        # Render a detailed view of the first trace
        if trace_ids:
            print("\n── Detailed trace view ──")
            render_trace(trace_ids[0], tracer=tracer)

        # Show cache stats
        stats = cached.cache_stats
        print(f"\nCache stats: {stats}")


if __name__ == "__main__":
    main()
