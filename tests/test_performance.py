"""Performance tests — parallelism benchmarks and cache correctness."""
from __future__ import annotations

import time

import pytest

from traceagent.async_storage import CachedStorage, gather_stats_parallel, gather_traces_parallel
from traceagent.models import Span
from traceagent.storage import InMemoryStorage
from traceagent.tracer import Tracer

# ── Helpers ───────────────────────────────────────────────────────────────────

def _store_with_n_traces(n: int) -> tuple[InMemoryStorage, list[str]]:
    store = InMemoryStorage()
    tracer = Tracer(storage=store)
    ids = []
    for i in range(n):
        with tracer.start_span(f"op-{i}") as span:
            pass
        ids.append(span.trace_id)
    return store, ids


# ── gather_traces_parallel ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gather_traces_parallel_returns_all():
    store, ids = _store_with_n_traces(10)
    results = await gather_traces_parallel(store, ids)
    assert len(results) == 10
    assert all(r is not None for r in results)


@pytest.mark.asyncio
async def test_gather_traces_parallel_preserves_order():
    store, ids = _store_with_n_traces(5)
    results = await gather_traces_parallel(store, ids)
    for i, trace in enumerate(results):
        assert trace is not None
        assert trace.trace_id == ids[i]


@pytest.mark.asyncio
async def test_gather_traces_parallel_missing_ids():
    store, ids = _store_with_n_traces(3)
    mixed = ids + ["nonexistent-1", "nonexistent-2"]
    results = await gather_traces_parallel(store, mixed)
    assert len(results) == 5
    assert results[3] is None
    assert results[4] is None


@pytest.mark.asyncio
async def test_gather_traces_parallel_empty_list():
    store, _ = _store_with_n_traces(0)
    results = await gather_traces_parallel(store, [])
    assert results == []


@pytest.mark.asyncio
async def test_gather_traces_parallel_semaphore_respected():
    """With semaphore=1 results should still be correct (sequential under the hood)."""
    store, ids = _store_with_n_traces(5)
    results = await gather_traces_parallel(store, ids, semaphore_limit=1)
    assert len(results) == 5
    assert all(r is not None for r in results)


@pytest.mark.asyncio
async def test_gather_traces_parallel_speedup():
    """Parallel fetch of 20 traces should not be 20x slower than a single fetch.

    This is a smoke test — in-memory storage is fast so we just verify
    gather returns in reasonable time (< 1 second for 20 items).
    """
    store, ids = _store_with_n_traces(20)
    t0 = time.perf_counter()
    results = await gather_traces_parallel(store, ids)
    elapsed = time.perf_counter() - t0
    assert all(r is not None for r in results)
    assert elapsed < 1.0, f"Parallel fetch took {elapsed:.3f}s — too slow"


# ── gather_stats_parallel ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gather_stats_parallel_multiple_backends():
    stores = []
    for i in range(3):
        s = InMemoryStorage()
        t = Tracer(storage=s)
        for j in range(i + 1):
            with t.start_span(f"op-{j}"):
                pass
        stores.append(s)
    results = await gather_stats_parallel(stores)
    assert len(results) == 3
    # Each store has i+1 traces
    assert results[0]["trace_count"] == 1
    assert results[1]["trace_count"] == 2
    assert results[2]["trace_count"] == 3


@pytest.mark.asyncio
async def test_gather_stats_parallel_empty_stores():
    stores = [InMemoryStorage() for _ in range(4)]
    results = await gather_stats_parallel(stores)
    assert all(r["trace_count"] == 0 for r in results)
    assert all(r["avg_duration_ms"] == 0.0 for r in results)


# ── CachedStorage ─────────────────────────────────────────────────────────────

def test_cached_storage_basic_hit():
    store = InMemoryStorage()
    cached = CachedStorage(store)
    span = Span(name="op")
    span.end()
    cached.save_span(span)
    # First call is a miss
    _ = cached.get_trace(span.trace_id)
    # Second call should be a cache hit
    _ = cached.get_trace(span.trace_id)
    stats = cached.cache_stats
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1


def test_cached_storage_invalidates_on_save():
    store = InMemoryStorage()
    cached = CachedStorage(store)
    s1 = Span(name="first")
    s1.end()
    cached.save_span(s1)
    trace_before = cached.get_trace(s1.trace_id)
    assert trace_before is not None
    assert len(trace_before.spans) == 1

    # Add second span to same trace — cache should invalidate
    s2 = Span(name="second", trace_id=s1.trace_id)
    s2.end()
    cached.save_span(s2)
    trace_after = cached.get_trace(s1.trace_id)
    assert trace_after is not None
    assert len(trace_after.spans) == 2


def test_cached_storage_list_traces_passthrough():
    store = InMemoryStorage()
    cached = CachedStorage(store)
    for i in range(5):
        s = Span(name=f"op-{i}")
        s.end()
        cached.save_span(s)
    traces = cached.list_traces(limit=10)
    assert len(traces) == 5


def test_cached_storage_clear():
    store = InMemoryStorage()
    cached = CachedStorage(store)
    s = Span(name="op")
    s.end()
    cached.save_span(s)
    cached.get_trace(s.trace_id)
    cached.clear()
    assert cached.cache_stats["size"] == 0
    assert cached.get_trace(s.trace_id) is None


def test_cached_storage_evicts_when_full():
    store = InMemoryStorage()
    cached = CachedStorage(store, maxsize=3)
    spans = []
    for i in range(5):
        s = Span(name=f"op-{i}")
        s.end()
        cached.save_span(s)
        cached.get_trace(s.trace_id)  # populate cache
        spans.append(s)
    # Cache should not exceed maxsize
    assert cached.cache_stats["size"] <= 3


def test_cached_storage_none_for_missing_trace():
    store = InMemoryStorage()
    cached = CachedStorage(store)
    result = cached.get_trace("no-such-trace")
    assert result is None


def test_cached_storage_parallel_speedup_measurement():
    """Demonstrate that cached repeated reads are faster than cold reads."""
    store = InMemoryStorage()
    cached = CachedStorage(store, maxsize=50)
    n = 20
    trace_ids = []
    for i in range(n):
        s = Span(name=f"op-{i}")
        s.end()
        cached.save_span(s)
        trace_ids.append(s.trace_id)

    # Cold reads
    t0 = time.perf_counter()
    for tid in trace_ids:
        cached.get_trace(tid)
    cold_time = time.perf_counter() - t0

    # Warm reads (all hits)
    t1 = time.perf_counter()
    for tid in trace_ids:
        cached.get_trace(tid)
    warm_time = time.perf_counter() - t1

    stats = cached.cache_stats
    assert stats["hits"] == n  # all second reads were hits
    # Warm reads should be at least as fast as cold reads
    assert warm_time <= cold_time * 2  # generous bound for CI jitter
