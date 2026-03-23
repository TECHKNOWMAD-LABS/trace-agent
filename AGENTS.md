# AGENTS.md — Edgecraft Autonomous Development Protocol

This repository was developed using the **Edgecraft Protocol** — an 8-cycle autonomous iteration system that transforms a seed codebase into a production-grade SDK without human intervention.

## Protocol Summary

Each cycle runs a distinct improvement loop: detect, conjecture, act, ground, and propagate lessons to the flywheel.

| Cycle | Name | Goal | Key Output |
|-------|------|------|-----------|
| 1 | Test Coverage | Achieve ≥90% line coverage | `conftest.py`, `test_dashboard.py`, coverage gap tests |
| 2 | Error Hardening | No crash on any valid or invalid input | Input validation, retry logic, 51 hardening tests |
| 3 | Performance | Identify and parallelise sequential I/O fan-outs | `async_storage.py` (gather + semaphore + LRU cache) |
| 4 | Security | No hardcoded secrets; no injection vectors | CWE-22 path traversal fix in `FileStorage` |
| 5 | CI/CD | Tests + lint on every push and PR | `.github/workflows/ci.yml`, `.pre-commit-config.yaml` |
| 6 | Property-Based Testing | Verify invariants across the input space | 17 Hypothesis tests; 2 real bugs found and fixed |
| 7 | Examples + Docs | Every public API has a working example | 3 runnable examples; complete docstring coverage |
| 8 | Release Engineering | Publishable artifact | `CHANGELOG.md`, `Makefile`, `pyproject.toml` metadata |

## Commit Taxonomy

Commits follow the RALF L-code taxonomy:

| Code | Meaning | Example |
|------|---------|---------|
| `L1/detection` | Identify a gap or problem | Coverage at 0% |
| `L2/noise` | Filter false positives | Security scan results |
| `L3/sub-noise` | Discover a genuine signal | Hypothesis edge case |
| `L4/conjecture` | Form a testable hypothesis | Parallelism will yield Nx speedup |
| `L5/action` | Implement a fix or improvement | Add validation, add CI |
| `L6/grounding` | Measure and verify | N tests passing, coverage = N% |
| `L7/flywheel` | Propagate lesson to related systems | Pattern applicable to other repos |

## Running the Protocol

```bash
# Install dependencies
make install

# Lint
make lint

# Full test suite with coverage
make coverage

# Run examples
make examples

# All CI checks
make check
```

## Architecture

```
src/traceagent/
├── models.py         # Span, Trace, SpanStatus — validated dataclasses
├── tracer.py         # Tracer, context-var active span, global singleton
├── storage.py        # BaseStorage, InMemoryStorage, FileStorage (with retry)
├── async_storage.py  # CachedStorage, gather_traces_parallel, gather_stats_parallel
├── decorators.py     # @trace, @trace_async
├── mcp_server.py     # MCPServer — list_traces, get_trace, get_stats tools
└── dashboard.py      # Rich terminal dashboard

tests/
├── conftest.py            # Shared fixtures
├── test_models.py         # Unit tests for models
├── test_tracer.py         # Unit tests for Tracer
├── test_storage.py        # Unit tests for storage backends
├── test_decorators.py     # Unit tests for decorators
├── test_mcp_server.py     # Unit tests for MCPServer
├── test_dashboard.py      # Unit tests for dashboard (was 0% coverage)
├── test_error_hardening.py # 51 edge-case / adversarial tests
├── test_performance.py    # Parallel fetch and cache benchmarks
└── test_properties.py     # 17 Hypothesis property-based tests

examples/
├── basic_tracing.py           # Nested spans, attributes, events
├── decorator_usage.py         # @trace/@trace_async + MCPServer
└── file_storage_dashboard.py  # FileStorage + CachedStorage + dashboard
```

## Security Notes

- `FileStorage` sanitises `trace_id` to `[a-zA-Z0-9\-_]` before constructing file paths (CWE-22 prevention)
- All storage methods validate input types and reject None/empty identifiers
- `MCPServer` never raises to callers — all errors are returned as JSON
- No hardcoded credentials, tokens, or API keys anywhere in the codebase

## Agent Attribution

Developed autonomously by Claude Sonnet 4.6 via the Edgecraft Protocol v4.0 for TechKnowMad Labs.
Repository: https://github.com/TECHKNOWMAD-LABS/trace-agent
