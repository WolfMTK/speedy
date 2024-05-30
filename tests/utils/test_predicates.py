import functools
from typing import Any

from speedy.utils import is_async_callable


def test_async_func() -> None:
    async def async_func() -> None:
        ...

    def func() -> None:
        ...

    assert is_async_callable(async_func)
    assert not is_async_callable(func)


def test_async_partial() -> None:
    async def async_func(a: Any, b: Any) -> None:
        ...

    def func(a: Any, b: Any) -> None:
        ...

    assert is_async_callable(functools.partial(async_func, 1))
    assert not is_async_callable(functools.partial(func, 1))


def test_async_method() -> None:
    class Async:
        async def method(self) -> None:
            ...

    class Sync:
        def method(self) -> None:
            ...

    assert is_async_callable(Async().method)
    assert not is_async_callable(Sync().method)


def test_async_object_call() -> None:
    class Async:
        async def __call__(self) -> None:
            ...

    class Sync:
        def __call__(self) -> None:
            ...

    assert is_async_callable(Async())
    assert not is_async_callable(Sync())


def test_async_partial_object_call() -> None:
    class Async:
        async def __call__(self, a: Any, b: Any) -> None:
            ...

    class Sync:
        def __call__(self, a: Any, b: Any) -> None:
            ...

    assert is_async_callable(functools.partial(Async(), 1))
    assert not is_async_callable(functools.partial(Sync(), 1))
