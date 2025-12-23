import asyncio
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Iterator
from unittest.mock import AsyncMock

import pytest
import trio
from pytest_mock import MockerFixture

from speedy.concurrency import sync_to_thread, get_asyncio_executor, set_asyncio_executor, get_trio_capacity_limiter, \
    set_trio_capacity_limiter


def func() -> int:
    return 1


@pytest.fixture
def loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


def test_sync_to_thread_asyncio(loop: asyncio.AbstractEventLoop) -> None:
    assert loop.run_until_complete(sync_to_thread(func)) == 1


def test_sync_to_thread_trio() -> None:
    assert trio.run(sync_to_thread, func) == 1


def test_get_set_asyncio_executor() -> None:
    assert get_asyncio_executor() is None
    executor = ThreadPoolExecutor()
    set_asyncio_executor(executor)
    assert get_asyncio_executor() is executor


def test_get_set_trio_capacity_limiter() -> None:
    limiter = trio.CapacityLimiter(10)
    assert get_trio_capacity_limiter() is None
    set_trio_capacity_limiter(limiter)
    assert get_trio_capacity_limiter() is limiter


def test_asyncio_uses_executor(mocker: MockerFixture, loop: asyncio.AbstractEventLoop) -> None:
    executor = ThreadPoolExecutor()

    mocker.patch("speedy.concurrency.get_asyncio_executor", return_value=executor)
    mock_run_in_executor = AsyncMock()
    mocker.patch("speedy.concurrency.asyncio.get_running_loop").return_value.run_in_executor = mock_run_in_executor

    loop.run_until_complete(sync_to_thread(func))
    assert mock_run_in_executor.call_args_list[0].args[0] is executor


def test_set_asyncio_executor_from_running_loop_raises(loop: asyncio.AbstractEventLoop) -> None:
    async def main() -> None:
        set_asyncio_executor(ThreadPoolExecutor())

    with pytest.raises(RuntimeError):
        loop.run_until_complete(main())

    assert get_asyncio_executor() is None
