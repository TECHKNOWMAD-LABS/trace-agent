"""Async parallel storage utilities for TraceAgent."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .models import Span, SpanStatus, Trace
from .storage import BaseStorage

logger = logging.getLogger(__name__)

_DEFAULT_SEMAPHORE = 10


async def gather_traces_parallel(
    storage: BaseStorage,
    trace_ids: list[str],
    *,
    semaphore_limit: int = _DEFAULT_SEMAPHORE,
) -> list[Trace | None]:
    """Fetch multiple traces concurrently using asyncio.gather with a semaphore.

    Sequential fetch of N traces takes O(N * I/O_latency).
    Parallel fetch reduces that to approximately O(I/O_latency) for small N.

    Args:
        storage: Storage backend to query.
        trace_ids: List of trace IDs to fetch.
        semaphore_limit: Maximum concurrent coroutines (default 10).

    Returns:
        List of Trace objects (or None for missing traces) in the same order as
        *trace_ids*.
    """
    sem = asyncio.Semaphore(semaphore_limit)

    async def _fetch(tid: str) -> Trace | None:
        async with sem:
            # Run blocking storage call in the default thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, storage.get_trace, tid)

    return list(await asyncio.gather(*[_fetch(tid) for tid in trace_ids]))


async def gather_stats_parallel(
    storages: list[BaseStorage],
    *,
    semaphore_limit: int = _DEFAULT_SEMAPHORE,
) -> list[dict[str, Any]]:
    """Fetch stats from multiple storage backends concurrently.

    Useful when a single MCPServer needs to aggregate across multiple
    storage shards.

    Args:
        storages: List of storage backends.
        semaphore_limit: Maximum concurrent coroutines.

    Returns:
        List of stat dicts (trace_count, error_count, avg_duration_ms).
    """
    sem = asyncio.Semaphore(semaphore_limit)

    async def _stat(store: BaseStorage) -> dict[str, Any]:
        async with sem:
            loop = asyncio.get_event_loop()
            traces = await loop.run_in_executor(None, lambda: store.list_traces(limit=1000))
            error_count = sum(
                1 for t in traces for s in t.spans if s.status == SpanStatus.ERROR
            )
            durations = [t.total_duration_ms for t in traces if t.total_duration_ms is not None]
            avg_ms = sum(durations) / len(durations) if durations else 0.0
            return {
                "trace_count": len(traces),
                "error_count": error_count,
                "avg_duration_ms": round(avg_ms, 2),
            }

    return list(await asyncio.gather(*[_stat(s) for s in storages]))


# ── Simple LRU cache for repeated trace lookups ────────────────────────────

class CachedStorage:
    """Wraps a BaseStorage with an LRU cache on get_trace.

    Repeated calls for the same trace_id are served from memory without
    hitting the underlying backend.  Cache is invalidated when save_span
    writes a new span for that trace.

    Args:
        storage: The underlying storage backend.
        maxsize: LRU cache capacity (number of trace_ids, default 128).
    """

    def __init__(self, storage: BaseStorage, maxsize: int = 128) -> None:
        self._storage = storage
        self._maxsize = maxsize
        self._cache: dict[str, Trace | None] = {}
        self._hits = 0
        self._misses = 0

    def save_span(self, span: Span) -> None:
        """Persist *span* and invalidate cache entry for its trace."""
        self._storage.save_span(span)
        # Invalidate so next read sees the updated trace
        self._cache.pop(span.trace_id, None)

    def get_trace(self, trace_id: str) -> Trace | None:
        """Return trace from cache if available, otherwise from storage."""
        if trace_id in self._cache:
            self._hits += 1
            return self._cache[trace_id]
        self._misses += 1
        trace = self._storage.get_trace(trace_id)
        if len(self._cache) >= self._maxsize:
            # Evict oldest entry (insertion-ordered dict in Python 3.7+)
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[trace_id] = trace
        return trace

    def list_traces(self, limit: int = 100) -> list[Trace]:
        """Pass-through to underlying storage (not cached)."""
        return self._storage.list_traces(limit=limit)

    def clear(self) -> None:
        """Clear both the underlying storage and the cache."""
        self._storage.clear()
        self._cache.clear()

    @property
    def cache_stats(self) -> dict[str, int]:
        """Return hit/miss/size stats for the cache."""
        return {"hits": self._hits, "misses": self._misses, "size": len(self._cache)}
