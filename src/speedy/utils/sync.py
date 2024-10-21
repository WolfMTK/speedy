from typing import TypeVar, ParamSpec, Awaitable, Callable

from speedy.concurrency import sync_to_thread
from speedy.utils.predicates import is_async_callable

P = ParamSpec('P')
T = TypeVar('T')


def ensure_async_callable(func: Callable[P, T]) -> Callable[P, Awaitable[T]]:
    """ Provide possibility of async object invocation. """
    if is_async_callable(func):
        return func
    return AsyncCallable(func)


class AsyncCallable:
    """ Wrapper a given callable to be called in a thread pool. """
    def __init__(self, function: Callable[P, T]) -> None:
        self.function = function

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Awaitable[T]:
        return sync_to_thread(self.function, *args, **kwargs)
