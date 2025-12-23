import asyncio
from typing import Any

import pytest
import trio

from speedy.utils._impl import (
    AsyncLibraryNotFoundError,
    current_async_library,
    _LIB_ASYNCIO,
    _LIB_TRIO,
)


@pytest.mark.parametrize(
    "library_name, runner",
    [
        (_LIB_ASYNCIO, lambda fn: asyncio.run(fn())),
        (_LIB_TRIO, lambda fn: trio.run(fn)),
    ],
)
def test_current_async_library(library_name: str, runner: Any) -> None:
    with pytest.raises(AsyncLibraryNotFoundError):
        current_async_library()

    ran = []

    async def check_library() -> None:
        assert current_async_library() == library_name
        ran.append(True)

    runner(check_library)

    assert ran == [True]

    with pytest.raises(AsyncLibraryNotFoundError):
        current_async_library()
