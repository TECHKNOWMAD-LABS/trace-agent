"""Decorators for automatic tracing."""
from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

from .tracer import get_tracer

F = TypeVar("F", bound=Callable[..., Any])


def trace(name: str | None = None, attributes: dict[str, Any] | None = None) -> Callable[[F], F]:
    """Decorator to trace a synchronous function."""

    def decorator(fn: F) -> F:
        span_name = name or f"{fn.__module__}.{fn.__qualname__}"

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_span(span_name, attributes=attributes):
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def trace_async(
    name: str | None = None, attributes: dict[str, Any] | None = None
) -> Callable[[F], F]:
    """Decorator to trace an async function."""

    def decorator(fn: F) -> F:
        span_name = name or f"{fn.__module__}.{fn.__qualname__}"

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_span(span_name, attributes=attributes):
                return await fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
