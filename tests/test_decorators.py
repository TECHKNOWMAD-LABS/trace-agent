"""Tests for trace decorators."""
import pytest

from traceagent.decorators import trace, trace_async
from traceagent.storage import InMemoryStorage
from traceagent.tracer import Tracer, set_global_tracer


def setup_tracer() -> Tracer:
    store = InMemoryStorage()
    t = Tracer(storage=store)
    set_global_tracer(t)
    return t


def test_trace_decorator_records_span():
    tracer = setup_tracer()

    @trace(name="my-func")
    def add(x, y):
        return x + y

    result = add(1, 2)
    assert result == 3
    traces = tracer.get_storage().list_traces()
    assert len(traces) == 1
    assert traces[0].spans[0].name == "my-func"


def test_trace_decorator_with_attributes():
    tracer = setup_tracer()

    @trace(name="tagged", attributes={"env": "test"})
    def noop():
        pass

    noop()
    traces = tracer.get_storage().list_traces()
    assert traces[0].spans[0].attributes["env"] == "test"


@pytest.mark.asyncio
async def test_trace_async_decorator():
    tracer = setup_tracer()

    @trace_async(name="async-op")
    async def fetch():
        return 42

    result = await fetch()
    assert result == 42
    traces = tracer.get_storage().list_traces()
    assert len(traces) == 1
    assert traces[0].spans[0].name == "async-op"
