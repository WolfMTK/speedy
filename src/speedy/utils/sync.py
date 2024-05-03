from collections.abc import Callable, Awaitable
from typing import TypeVar, ParamSpec

from speedy.concurrency import sync_to_thread

P = ParamSpec('P')
T = TypeVar('T')


class AsyncCallable:
    def __init__(self, function: Callable[P, T]) -> None:
        self.function = function

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Awaitable[T]:
        return sync_to_thread(self.function, *args, **kwargs)
