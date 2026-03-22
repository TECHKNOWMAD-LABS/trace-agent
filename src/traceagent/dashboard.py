"""Rich text dashboard for TraceAgent."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import SpanStatus
from .tracer import Tracer, get_tracer

_STATUS_COLOR = {
    SpanStatus.OK: "green",
    SpanStatus.ERROR: "red",
    SpanStatus.UNSET: "yellow",
}


def render_dashboard(tracer: Tracer | None = None, limit: int = 20) -> None:
    """Print a Rich dashboard of recent traces to stdout."""
    t = tracer or get_tracer()
    console = Console()

    traces = t.get_storage().list_traces(limit=limit)
    stats_table = Table(title="TraceAgent Stats", show_header=True, header_style="bold cyan")
    stats_table.add_column("Metric", style="bold")
    stats_table.add_column("Value", justify="right")

    error_count = sum(1 for tr in traces for s in tr.spans if s.status == SpanStatus.ERROR)
    durations = [tr.total_duration_ms for tr in traces if tr.total_duration_ms is not None]
    avg_ms = sum(durations) / len(durations) if durations else 0.0

    stats_table.add_row("Total Traces", str(len(traces)))
    stats_table.add_row("Error Spans", str(error_count))
    stats_table.add_row("Avg Duration (ms)", f"{avg_ms:.1f}")
    console.print(stats_table)

    trace_table = Table(title="Recent Traces", show_header=True, header_style="bold magenta")
    trace_table.add_column("Trace ID", style="dim", width=18)
    trace_table.add_column("Root Span")
    trace_table.add_column("Spans", justify="right")
    trace_table.add_column("Duration (ms)", justify="right")
    trace_table.add_column("Status")

    for trace in traces:
        root = trace.root_span
        status = root.status if root else SpanStatus.UNSET
        color = _STATUS_COLOR[status]
        trace_table.add_row(
            trace.trace_id[:16] + "…",
            root.name if root else "—",
            str(len(trace.spans)),
            f"{trace.total_duration_ms:.1f}" if trace.total_duration_ms is not None else "—",
            Text(status.value, style=color),
        )
    console.print(trace_table)


def render_trace(trace_id: str, tracer: Tracer | None = None) -> None:
    """Print a detailed view of a single trace."""
    t = tracer or get_tracer()
    console = Console()
    trace = t.get_storage().get_trace(trace_id)
    if trace is None:
        console.print(f"[red]Trace {trace_id!r} not found[/red]")
        return

    table = Table(title=f"Trace {trace_id[:16]}…", show_header=True, header_style="bold")
    table.add_column("Span")
    table.add_column("Parent")
    table.add_column("Duration (ms)", justify="right")
    table.add_column("Status")
    table.add_column("Error")

    for span in trace.spans:
        color = _STATUS_COLOR[span.status]
        table.add_row(
            span.name,
            span.parent_id[:8] + "…" if span.parent_id else "—",
            f"{span.duration_ms:.1f}" if span.duration_ms is not None else "—",
            Text(span.status.value, style=color),
            span.error or "",
        )
    console.print(Panel(table))
