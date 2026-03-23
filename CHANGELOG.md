# Changelog

All notable changes to `traceagent` are documented here.

## [0.1.0] — 2026-03-23

### Added

**Cycle 1 — Test Coverage (0% → 100%)**
- `tests/conftest.py`: shared fixtures (`memory_storage`, `tracer`, `file_storage`, `tmp_dir`) and `make_span` / `make_trace_with_spans` helpers
- `tests/test_dashboard.py`: 12 tests covering `render_dashboard` and `render_trace` — all code paths including empty tracer, error spans, parent-child display, and global tracer fallback
- Edge-case tests for `Trace.total_duration_ms` (no root span), `FileStorage` append-to-existing branch, `get_trace` missing file, and `get_tracer` singleton creation

**Cycle 2 — Error Hardening**
- `Span.__post_init__`: validates name is non-empty, non-None string; truncates to 512 chars
- `Span.add_event`: validates event name; rejects non-dict attributes; truncates huge event names
- `Span.set_attribute`: validates key type; rejects None/empty keys; truncates string values to 4096 chars
- `Span.end`: truncates error messages to 8192 chars
- `Trace.add_span`: rejects non-Span arguments
- `InMemoryStorage` / `FileStorage`: validate span type, trace_id, and limit arguments
- `FileStorage`: 3-attempt exponential back-off retry on `save_span` I/O; skips corrupt JSON files in `list_traces`
- `MCPServer.call_tool`: validates tool name type; returns error JSON instead of raising; handles missing `trace_id` key gracefully
- `_coerce_limit`: handles None, non-numeric, negative, and huge limit values
- `tests/test_error_hardening.py`: 51 tests covering all error paths

**Cycle 3 — Performance**
- `src/traceagent/async_storage.py`: new module with:
  - `gather_traces_parallel`: asyncio.gather with semaphore for concurrent trace fetching (pattern applicable to I/O-bound FileStorage and remote OTLP backends)
  - `gather_stats_parallel`: concurrent stats aggregation across multiple storage shards
  - `CachedStorage`: LRU cache wrapper with hit/miss tracking and automatic invalidation on write
- `tests/test_performance.py`: 15 tests for parallel fetch, cache correctness, and eviction

**Cycle 4 — Security**
- Fixed CWE-22 path traversal vulnerability in `FileStorage._trace_file()`: trace_id is now sanitised to `[a-zA-Z0-9\-_]` and the resolved path is verified to remain inside the storage directory before any file access

**Cycle 5 — CI/CD**
- `.github/workflows/ci.yml`: matrix CI over Python 3.9/3.11/3.12 with ruff lint, pytest with `--cov-fail-under=90`, and coverage artifact upload
- `.pre-commit-config.yaml`: ruff + ruff-format + mypy pre-commit hooks
- Fixed 19 ruff lint violations (unused imports, line length, F841 unused variables)

**Cycle 6 — Property-Based Testing**
- `tests/test_properties.py`: 17 Hypothesis property tests across 8 strategies
- Hypothesis found and fixed 2 real bugs:
  1. `list_traces(limit=0)` returned all traces (Python slice `[-0:]` equals `[0:]`)
  2. `_coerce_limit(float('inf'))` raised `OverflowError` (missing `OverflowError` in except clause)

**Cycle 7 — Examples + Docs**
- `examples/basic_tracing.py`: nested spans, attributes, events, and error capture
- `examples/decorator_usage.py`: `@trace` / `@trace_async` decorators + MCPServer query interface
- `examples/file_storage_dashboard.py`: `FileStorage` + `CachedStorage` + Rich dashboard rendering
- Complete docstrings added to every public function in all modules

**Cycle 8 — Release Engineering**
- `pyproject.toml`: added `authors`, `keywords`, `classifiers`, and `mypy` tool config
- `CHANGELOG.md`: this file
- `Makefile`: `test`, `lint`, `format`, `security`, `coverage`, `clean` targets
- `AGENTS.md`: autonomous development protocol documentation
- `EVOLUTION.md`: per-cycle findings, timestamps, and metrics

### Changed
- `pyproject.toml` `[project.optional-dependencies.dev]`: added `pytest-cov`, `hypothesis`, `mypy`

### Fixed
- `InMemoryStorage.list_traces(limit=0)` now correctly returns `[]`
- `_coerce_limit(float('inf'))` now returns the default limit instead of raising
- `FileStorage._trace_file()` now prevents path traversal attacks (CWE-22)
