# TraceAgent

**Version**: 0.1.0
**License**: MIT
**Package**: `traceagent`

## Overview

Lightweight Python observability SDK providing distributed tracing, span management, pluggable storage, function decorators, an MCP-compatible server, and a Rich terminal dashboard.

## Components

| Module | Purpose |
|--------|---------|
| `models` | `Span`, `Trace`, `SpanStatus` data classes |
| `tracer` | `Tracer` context-manager based span lifecycle |
| `storage` | `InMemoryStorage`, `FileStorage` backends |
| `decorators` | `@trace`, `@trace_async` function instrumentation |
| `mcp_server` | `MCPServer` exposing `list_traces`, `get_trace`, `get_stats` |
| `dashboard` | `render_dashboard`, `render_trace` via Rich |

## Quick Start

```python
from traceagent import get_tracer, trace

tracer = get_tracer()

# Context manager
with tracer.start_span("my-operation", attributes={"user": "alice"}) as span:
    span.add_event("cache_miss")
    # ... your code ...

# Decorator
@trace(name="process-request")
def handle(req):
    ...

# Dashboard
from traceagent.dashboard import render_dashboard
render_dashboard()
```

## MCP Server

```python
from traceagent.mcp_server import MCPServer
server = MCPServer()
print(server.call_tool("get_stats"))
```

## Storage Backends

```python
from traceagent import FileStorage, Tracer
tracer = Tracer(storage=FileStorage("/tmp/traces"))
```
