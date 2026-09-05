import functools
from typing import Callable, Iterator, AsyncIterator, Iterable

import anyio.to_thread


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
