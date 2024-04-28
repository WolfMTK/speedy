import asyncio
import contextvars
import functools
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TypeVar, ParamSpec, Callable

import sniffio

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


async def sync_to_thread(
        obj: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs
) -> T:
    """
    Run a synchronous call to an object in an asynchronous thread.
    """
    match sniffio.current_async_library():
        case 'asyncio':
            return await _run_sync_asyncio(obj, *args, **kwargs)
        case _:
            raise RuntimeError('Unsupported async library')


def get_asyncio_executor() -> ThreadPoolExecutor | None:
    """
    Getting the executor in which to execute synchronous calls
    in asyncio context.
    """

    return _State.EXECUTOR
