import functools
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Generator, Iterable, Iterator
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, TypeGuard, TypeVar

import anyio.to_thread

if sys.version_info >= (3, 13):
    from inspect import iscoroutinefunction
else:
    from asyncio import iscoroutinefunction


async def run_in_threadpool[**P, T](func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    func = functools.partial(func, *args, **kwargs)
    return await anyio.to_thread.run_sync(func)


def _next_batch[T](iterator: Iterator[T], batch_size: int) -> tuple[list[T], bool]:
    items: list[T] = []
    for _ in range(batch_size):
        try:
            items.append(next(iterator))
        except StopIteration:
            return items, True
    return items, False


async def iterate_in_threadpool[T](
    iterator: Iterable[T],
    batch_size: int = 1,
) -> AsyncIterator[T]:
    as_iterator = iter(iterator)
    while True:
        items, exhausted = await anyio.to_thread.run_sync(_next_batch, as_iterator, batch_size)
        for item in items:
            yield item
        if exhausted:
            break


def is_async_callable[**P, T](obj: Callable[P, T]) -> TypeGuard[Callable[P, Awaitable[T]]]:
    obj = unwrap_partial(obj)

    return iscoroutinefunction(obj) or (callable(obj) and iscoroutinefunction(obj.__call__))


def unwrap_partial(value: Callable[..., Any]) -> Callable[..., Any]:
    if isinstance(value, functools.partial):
        return value.func
    if isinstance(value, AsyncCallable):
        return value.function
    return value


class AsyncCallable[**P, T]:
    def __init__(self, function: Callable[P, T]) -> None:
        self.function = function

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Awaitable[T]:
        return run_in_threadpool(self.function, *args, **kwargs)


class AwaitableOrContextManager[T_co](Awaitable[T_co], AbstractAsyncContextManager[T_co], Protocol[T_co]): ...


class SupportsAsyncClose(Protocol):
    async def close(self) -> None: ...


SupportsAsyncCloseType = TypeVar("SupportsAsyncCloseType", bound=SupportsAsyncClose)


class AwaitableOrContextManagerWrapper:
    __slots__ = ("aw", "entered")

    def __init__(self, aw: Awaitable[Any]) -> None:
        self.aw = aw

    def __await__(self) -> Generator[Any, None, Any]:
        return self.aw.__await__()

    async def __aenter__(self) -> Any:
        self.entered = await self.aw
        return self.entered

    async def __aexit__(self, *args: Any) -> None:
        await self.entered.close()
