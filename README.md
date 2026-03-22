# TraceAgent

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)

Lightweight Python observability SDK for distributed tracing and span management. No external collectors required.

---

## Features

- **Context-manager spans** — Start and close spans with `with tracer.start_span(...)`, automatically capturing start/end time and duration.
- **Decorator instrumentation** — Wrap any sync or async function with `@trace` / `@trace_async`; exceptions are captured and the span marked as ERROR.
- **Pluggable storage** — Ships with `InMemoryStorage` (default) and `FileStorage` for persistent, file-backed traces.
- **MCP server** — Expose live trace data over the Model Context Protocol via `list_traces`, `get_trace`, and `get_stats` tools.
- **Rich terminal dashboard** — Render traces and aggregate statistics in the terminal using the `dashboard` module.
- **Thread- and async-safe** — Storage is protected by threading locks; active-span tracking uses `contextvars.ContextVar` for correct async isolation.

---

## Installation

```bash
pip install traceagent          # production
pip install "traceagent[dev]"   # includes pytest, pytest-asyncio, ruff
```

Or from source:

```bash
git clone https://github.com/techknowmad/trace-agent.git
cd trace-agent
pip install -e ".[dev]"
```

---

## Quick Start

```python
from traceagent import get_tracer, trace, trace_async

# --- Context manager ---
tracer = get_tracer()

with tracer.start_span("db.query", attributes={"table": "users"}) as span:
    span.add_event("cache_miss")
    rows = fetch_rows()          # your code here

# --- Sync decorator ---
@trace(name="process-request")
def handle(request):
    return {"ok": True}

# --- Async decorator ---
@trace_async(name="fetch-data")
async def fetch(url: str):
    async with httpx.AsyncClient() as client:
        return await client.get(url)

# --- Persistent storage ---
from traceagent import FileStorage, Tracer

tracer = Tracer(storage=FileStorage("/tmp/traces"))

with tracer.start_span("batch-job") as span:
    span.set_attribute("records", 1_000)
```

---

## MCP Server

```python
from traceagent.mcp_server import MCPServer

server = MCPServer()

# List all recorded traces
traces = server.call_tool("list_traces")

# Retrieve a specific trace by ID
trace  = server.call_tool("get_trace", {"trace_id": "<id>"})

# Aggregate statistics
stats  = server.call_tool("get_stats")
```

---

## Architecture

```
traceagent/
├── models.py        # Span, Trace, SpanStatus — pure dataclasses, no I/O
├── tracer.py        # Tracer — span lifecycle, ContextVar active-span tracking
├── storage.py       # InMemoryStorage, FileStorage — thread-safe backends
├── decorators.py    # @trace, @trace_async — wraps functions, captures errors
├── mcp_server.py    # MCPServer — MCP-protocol tool surface over live storage
└── dashboard.py     # Rich-powered terminal renderer for traces and stats
```

**Data flow:**

```
caller
  └─ Tracer.start_span()
       ├─ creates Span (model)
       ├─ sets ContextVar (active span)
       └─ on __exit__ / exception
            ├─ records end_time, duration_ms, SpanStatus
            └─ Storage.save_span()
                  ├─ InMemoryStorage  →  dict in process memory
                  └─ FileStorage      →  JSON files on disk

MCPServer
  └─ reads from Storage → serves list_traces / get_trace / get_stats
```

---

## Development

```bash
# Run all tests
pytest -v

# Lint
ruff check .

# Run a single test module
pytest tests/test_tracer.py -v
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for branching conventions, code style, and pull-request guidelines.

---

## License

[MIT](LICENSE) © 2026 TechKnowMad Labs Private Limited

---

Built by [TechKnowMad Labs](https://techknowmad.ai)
