from __future__ import annotations

import asyncio
import contextvars
import functools
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TypeVar, ParamSpec, Callable, TYPE_CHECKING

from speedy.utils._impl import current_async_library, AsyncLibraryNotFoundError

if TYPE_CHECKING:
    import trio

T = TypeVar('T')
P = ParamSpec('P')


@dataclass
class _State:
    EXECUTOR: ThreadPoolExecutor | None = None
    LIMITER: ThreadPoolExecutor | None = None


async def _run_sync_asyncio(
        obj: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs
) -> T:
    ctx = contextvars.copy_context()
    bound_function = functools.partial(ctx.run, obj, *args, **kwargs)
    get_loop = asyncio.get_running_loop()
    return await get_loop.run_in_executor(
        get_asyncio_executor(),
        bound_function
    )


async def _run_sync_trio(
        obj: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs
) -> T:
    import trio

    bound_function = functools.partial(obj, *args, **kwargs)
    return await trio.to_thread.run_sync(
        bound_function,
        limiter=get_trio_capacity_limiter(),
    )


async def sync_to_thread(
        obj: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs
) -> T:
    """ Run a synchronous call to an object in an asynchronous thread. """
    match current_async_library():
        case 'asyncio':
            return await _run_sync_asyncio(obj, *args, **kwargs)
        case "trio":
            return await _run_sync_trio(obj, *args, **kwargs)
        case _:
            raise RuntimeError('Unsupported async library')


def set_asyncio_executor(executor: ThreadPoolExecutor | None) -> None:
    """ Set the executor in which synchronous callables will be run within an asyncio context. """
    try:
        current_async_library()
    except AsyncLibraryNotFoundError:
        pass
    else:
        raise RuntimeError("Cannot set executor fron running loop")

    _State.EXECUTOR = executor


def get_asyncio_executor() -> ThreadPoolExecutor | None:
    """ Getting the executor in which to execute synchronous calls in asyncio context. """
    return _State.EXECUTOR


def get_trio_capacity_limiter() -> trio.CapacityLimiter | None:
    """ Get the capacity limiter user when running synchronous callable within a trio context. """
    return _State.LIMITER


def set_trio_capacity_limiter(limiter: trio.CapacityLimiter | None) -> None:
    try:
        current_async_library()
    except AsyncLibraryNotFoundError:
        pass
    else:
        raise RuntimeError("Cannot set limiter while in async context")

    _State.LIMITER = limiter
