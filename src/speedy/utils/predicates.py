import asyncio
from typing import TypeVar, ParamSpec, Callable, TypeGuard, Awaitable

from .helpers import unwrap_partial

P = ParamSpec('P')
T = TypeVar('T')


def is_async_callable(
        obj: Callable[P, T]
) -> TypeGuard[Callable[P, Awaitable[T]]]:
    obj = unwrap_partial(obj)

    return asyncio.iscoroutinefunction(obj) or (
            callable(obj) and
            asyncio.iscoroutinefunction(obj.__call__)  # type: ignore[operator]
    )
