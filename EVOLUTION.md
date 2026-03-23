# EVOLUTION.md — 8-Cycle Edgecraft Iteration Log

Repository: `TECHKNOWMAD-LABS/trace-agent`
Protocol: Edgecraft v4.0
Agent: Claude Sonnet 4.6
Date: 2026-03-23

---

## Cycle 1 — Test Coverage

**Timestamp:** 2026-03-23T00:00
**Duration:** ~5 minutes

**Findings:**
- `dashboard.py`: 0% coverage (51 statements, 51 missed)
- `models.py`: 98% (1 missed — `total_duration_ms` no-root branch)
- `storage.py`: 97% (2 missed — FileStorage append and missing-file branches)
- `tracer.py`: 98% (1 missed — `get_tracer` global creation path)

**Actions:**
- Created `tests/conftest.py` with shared fixtures and helper factories
- Created `tests/test_dashboard.py` with 12 tests covering all dashboard code paths
- Added 5 targeted tests to fill remaining gaps in models, storage, and tracer

**Result:** 47 tests passing, 100% coverage

---

## Cycle 2 — Error Hardening

**Timestamp:** 2026-03-23T00:05
**Duration:** ~10 minutes

**Findings:**
- `Span(name=None)` caused `AttributeError` in `uuid4().hex` call chain
- `Span(name="")` silently created spans with empty names
- `Span(name="x"*100_000)` stored unbounded string in memory
- `Span.set_attribute(None, v)` stored `None` as a dict key
- `Span.end(error="x"*200_000)` stored unbounded error string
- `FileStorage(None)` raised `AttributeError` instead of `ValueError`
- `FileStorage.list_traces("bad")` raised `TypeError` without message
- `MCPServer.call_tool("get_trace", {})` raised `KeyError` on missing `trace_id`
- `MCPServer.call_tool(None)` raised `AttributeError`

**Actions:**
- Added `_validate_name()` with None/type/empty checks and 512-char truncation
- Added type/size validation to all public API entry points
- Added 3-attempt exponential back-off retry to `FileStorage.save_span`
- Added corrupt-file skip logic to `FileStorage.list_traces`
- Created `tests/test_error_hardening.py` with 51 tests

**Result:** 98 tests passing; no crashes on any tested invalid input

---

## Cycle 3 — Performance

**Timestamp:** 2026-03-23T00:15
**Duration:** ~8 minutes

**Findings:**
- No existing parallelism: all trace fetches were sequential
- Repeated `get_trace` calls for the same ID hit storage every time (no caching)
- Multi-shard aggregation (multiple storage backends) was not supported

**Actions:**
- Created `async_storage.py` with `gather_traces_parallel` (asyncio + semaphore)
- Created `gather_stats_parallel` for concurrent multi-backend aggregation
- Created `CachedStorage` LRU wrapper with hit/miss tracking and write invalidation
- Created `tests/test_performance.py` with 15 tests

**Measurement (in-memory backend):**
- Sequential 50 traces: 0.05ms
- Parallel 50 traces: 3.53ms (asyncio overhead dominates for in-memory)
- Pattern benefit realised with FileStorage or remote OTLP backends where each call has real I/O latency

**Note:** For in-process in-memory storage, `CachedStorage` is more impactful than parallelism — repeated reads show 0x dict overhead vs re-entrant lock acquisition.

---

## Cycle 4 — Security

**Timestamp:** 2026-03-23T00:23
**Duration:** ~5 minutes

**Scan Results:** 1 real finding, 2 false positives

| Finding | File | Type | Disposition |
|---------|------|------|-------------|
| Path traversal via `trace_id` | `storage.py:212` | CWE-22 | FIXED |
| `token` variable | `tracer.py:38` | False positive — ContextVar reset token | Documented |
| `run_in_executor` | `async_storage.py:44` | False positive — not an injection vector | Documented |

**Fix:**
- `FileStorage._safe_filename()`: strips `trace_id` to `[a-zA-Z0-9\-_]`
- `FileStorage._trace_file()`: verifies resolved path starts with storage directory root

---

## Cycle 5 — CI/CD

**Timestamp:** 2026-03-23T00:28
**Duration:** ~5 minutes

**Actions:**
- Created `.github/workflows/ci.yml`:
  - Matrix: Python 3.9, 3.11, 3.12
  - Steps: checkout → setup-python → install deps → ruff check → pytest with coverage
  - Coverage artifact upload (Python 3.12 only)
- Created `.pre-commit-config.yaml`: ruff, ruff-format, mypy hooks
- Fixed 19 ruff violations: unused imports, line length, unused variables

---

## Cycle 6 — Property-Based Testing

**Timestamp:** 2026-03-23T00:33
**Duration:** ~8 minutes

**Properties verified:**
1. `Span.name` always non-empty after construction (200 examples)
2. `duration_ms` is None before end, non-negative after end
3. Non-empty `error` always forces `ERROR` status
4. `set_attribute` stores every key (possibly truncated)
5. `add_event` always increases events count by 1
6. `Span.to_dict()` always produces valid JSON
7. Trace span count matches adds
8. `_validate_limit` always returns value in [0, 10000]
9. `_coerce_limit` never raises for any input
10. `MCPServer.call_tool` always returns valid JSON

**Bugs found by Hypothesis:**

| Bug | Input | Failure | Fix |
|-----|-------|---------|-----|
| `list_traces(limit=0)` returned all traces | `limit=0` | `[-0:]` equals `[0:]` in Python | Guard `if limit == 0: return []` |
| `_coerce_limit(inf)` raised OverflowError | `float('inf')` | `int(inf)` overflows | Added `OverflowError` to except clause |

**Result:** 17 property tests, 2 bugs fixed, 130 total tests passing

---

## Cycle 7 — Examples + Docs

**Timestamp:** 2026-03-23T00:41
**Duration:** ~6 minutes

**Examples created:**
1. `examples/basic_tracing.py` — nested spans, attributes, events, error capture
2. `examples/decorator_usage.py` — @trace/@trace_async decorators + MCPServer
3. `examples/file_storage_dashboard.py` — FileStorage + CachedStorage + Rich dashboard

All 3 examples tested and execute successfully.

**Docstrings:** Complete Google-style docstrings added to every public function in all 7 source modules.

---

## Cycle 8 — Release Engineering

**Timestamp:** 2026-03-23T00:47
**Duration:** ~5 minutes

**Actions:**
- `pyproject.toml`: added `authors`, `keywords`, `classifiers`, mypy config, dev deps
- `CHANGELOG.md`: full history of all 8 cycles
- `Makefile`: `install`, `test`, `coverage`, `lint`, `format`, `typecheck`, `examples`, `clean`, `check`
- `AGENTS.md`: protocol documentation and architecture overview
- `EVOLUTION.md`: this file
- Git tag: `v0.1.0`

---

## Final Metrics

| Metric | Before | After |
|--------|--------|-------|
| Tests | 30 | 130 |
| Coverage | 81% | 100% |
| Modules covered | 4/7 | 7/7 |
| Security findings fixed | — | 1 (CWE-22) |
| Bugs found by Hypothesis | — | 2 |
| Examples | 0 | 3 |
| CI pipeline | None | GitHub Actions (3-version matrix) |
| Git commits | 0 | 14 |
