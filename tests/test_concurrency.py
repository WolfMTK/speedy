import threading
from collections.abc import Iterator
from contextvars import ContextVar

import pytest
from speedy.concurrency import run_in_threadpool, _next_batch, iterate_in_threadpool


@pytest.mark.anyio
async def test_positional_args() -> None:
    def add(a: int, b: int) -> int:
        return a + b

    assert await run_in_threadpool(add, 2, 3) == 5


@pytest.mark.anyio
async def test_keyword_args() -> None:
    def greet(name: str, *, greeting: str = "hello") -> str:
        return f"{greeting}, {name}"

    assert await run_in_threadpool(greet, "world", greeting="hi") == "hi, world"


@pytest.mark.anyio
async def test_no_args() -> None:
    def constant() -> int:
        return 42

    assert await run_in_threadpool(constant) == 42


@pytest.mark.anyio
async def test_runs_in_a_different_thread() -> None:
    caller_thread = threading.get_ident()

    def get_thread_id() -> int:
        return threading.get_ident()

    worker_thread = await run_in_threadpool(get_thread_id)
    assert worker_thread != caller_thread


@pytest.mark.anyio
async def test_propagates_exception() -> None:
    def boom() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await run_in_threadpool(boom)


def test_fewer_items_than_batch_size_exhausts() -> None:
    items, exhausted = _next_batch(iter([1, 2]), batch_size=5)
    assert items == [1, 2]
    assert exhausted is True


def test_exactly_batch_size_does_not_report_exhausted() -> None:
    items, exhausted = _next_batch(iter([1, 2, 3]), batch_size=3)
    assert items == [1, 2, 3]
    assert exhausted is False


def test_more_items_than_batch_size_leaves_remainder() -> None:
    iterator = iter([1, 2, 3, 4, 5])
    items, exhausted = _next_batch(iterator, batch_size=2)
    assert items == [1, 2]
    assert exhausted is False
    assert list(iterator) == [3, 4, 5]


def test_already_exhausted_iterator() -> None:
    empty: Iterator[int] = iter([])
    items, exhausted = _next_batch(empty, batch_size=4)
    assert items == []
    assert exhausted is True


def test_batch_size_one_matches_single_next() -> None:
    iterator = iter([1, 2, 3])
    items, exhausted = _next_batch(iterator, batch_size=1)
    assert items == [1]
    assert exhausted is False


@pytest.mark.anyio
async def test_basic_iteration() -> None:
    class CustomIterable:
        def __iter__(self) -> Iterator[int]:
            yield from range(3)

    assert [v async for v in iterate_in_threadpool(CustomIterable())] == [0, 1, 2]


@pytest.mark.anyio
async def test_plain_list() -> None:
    assert [v async for v in iterate_in_threadpool([1, 2, 3])] == [1, 2, 3]


@pytest.mark.anyio
async def test_empty_iterable() -> None:
    empty: list[int] = []
    assert [v async for v in iterate_in_threadpool(empty)] == []


@pytest.mark.anyio
async def test_generator_source() -> None:
    def gen() -> Iterator[int]:
        yield 1
        yield 2
        yield 3

    assert [v async for v in iterate_in_threadpool(gen())] == [1, 2, 3]


@pytest.mark.anyio
@pytest.mark.parametrize("batch_size", [1, 2, 3, 4, 10])
async def test_preserves_order_across_batch_sizes(batch_size: int) -> None:
    data = list(range(7))
    result = [v async for v in iterate_in_threadpool(data, batch_size=batch_size)]
    assert result == data


@pytest.mark.anyio
async def test_batch_size_larger_than_source_is_not_exhausted_early() -> None:
    result = [v async for v in iterate_in_threadpool([1, 2], batch_size=100)]
    assert result == [1, 2]


@pytest.mark.anyio
async def test_non_stop_iteration_error_propagates() -> None:
    def gen() -> Iterator[int]:
        yield 1
        raise RuntimeError("iterator broke")

    collected: list[int] = []
    with pytest.raises(RuntimeError, match="iterator broke"):
        async for v in iterate_in_threadpool(gen()):
            collected.append(v)
    assert collected == [1]


@pytest.mark.anyio
async def test_runs_in_a_different_thread() -> None:
    caller_thread = threading.get_ident()

    def gen() -> Iterator[int]:
        yield threading.get_ident()

    result = [v async for v in iterate_in_threadpool(gen())]
    assert result != [caller_thread]
