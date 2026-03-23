"""Example 2 — Using @trace and @trace_async decorators.

Demonstrates automatic tracing of sync and async functions with the
@trace / @trace_async decorators and the MCPServer query interface.

Run:
    python examples/decorator_usage.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "src")  # allow running from repo root without installing

from traceagent import InMemoryStorage, Tracer, trace, trace_async
from traceagent.mcp_server import MCPServer
from traceagent.tracer import set_global_tracer
import json


# ── Setup a global tracer ──────────────────────────────────────────────────────

storage = InMemoryStorage()
tracer = Tracer(name="decorator-example", storage=storage)
set_global_tracer(tracer)


# ── Decorated sync function ───────────────────────────────────────────────────

@trace(name="process.record", attributes={"component": "etl"})
def process_record(record_id: int) -> dict:
    """Simulate processing a single record."""
    return {"id": record_id, "status": "processed"}


# ── Decorated async function ──────────────────────────────────────────────────

@trace_async(name="fetch.data", attributes={"source": "api"})
async def fetch_data(endpoint: str) -> list:
    """Simulate an async API fetch."""
    await asyncio.sleep(0.005)
    return [{"item": i} for i in range(3)]


# ── Driver ────────────────────────────────────────────────────────────────────

async def main() -> None:
    # Sync decorated calls
    for i in range(5):
        process_record(i)

    # Async decorated call
    data = await fetch_data("/items")
    print(f"Fetched {len(data)} items")

    # Query via MCPServer
    server = MCPServer(tracer=tracer)

    # list_traces
    list_result = json.loads(server.call_tool("list_traces", {"limit": 10}))
    print(f"\nlist_traces returned {list_result['total']} traces")

    # get_stats
    stats = json.loads(server.call_tool("get_stats"))
    print(f"Stats: {stats}")

    # get_trace for first trace
    if list_result["traces"]:
        tid = list_result["traces"][0]["trace_id"]
        trace_data = json.loads(server.call_tool("get_trace", {"trace_id": tid}))
        print(f"\nFirst trace detail: spans={trace_data['span_count']}, "
              f"duration={trace_data.get('total_duration_ms', 0):.2f}ms")


if __name__ == "__main__":
    asyncio.run(main())
