from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Callable, AsyncGenerator
from unittest.mock import AsyncMock

import pytest

from speedy import Speedy
from speedy.testing import create_test_client
from speedy.testing.client import TestClient


@pytest.fixture
def startup_mock() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def shutdown_mock() -> AsyncMock:
    return AsyncMock()


LifeSpanManager = Callable[[Speedy], "AbstractAsyncContextManager[None]"]


def create_lifespan_manager(startup_mock: AsyncMock, shutdown_mock: AsyncMock) -> LifeSpanManager:
    @asynccontextmanager
    async def lifespan(app: Speedy) -> AsyncGenerator[None, None]:
        try:
            await startup_mock(app)
            yield
        finally:
            await shutdown_mock()

    return lifespan


@pytest.fixture
def lifespan_manager(
        startup_mock: AsyncMock,
        shutdown_mock: AsyncMock,
) -> LifeSpanManager:
    return create_lifespan_manager(startup_mock, shutdown_mock)


def tets_lifespan_context_manager(
        lifespan_manager: LifeSpanManager,
        startup_mock: AsyncMock,
        shutdown_mock: AsyncMock,
) -> None:
    with create_test_client(lifespan=[lifespan_manager]):
        assert startup_mock.call_count == 1
        assert shutdown_mock.call_count == 0

    assert shutdown_mock.call_count == 1


def test_lifespan_context_manager_with_hooks(
        lifespan_manager: LifeSpanManager,
        startup_mock: AsyncMock,
        shutdown_mock: AsyncMock,
) -> None:
    on_startup_hook_mock = AsyncMock()
    on_shutdown_hook_mock = AsyncMock()

    async def on_startup() -> None:
        await on_startup_hook_mock()

    async def on_shutdown() -> None:
        await on_shutdown_hook_mock()

    with create_test_client(
            lifespan=[lifespan_manager],
            on_startup=[on_startup],
            on_shutdown=[on_shutdown],
    ):
        assert startup_mock.call_count == 1
        assert on_startup_hook_mock.call_count == 1
        assert shutdown_mock.call_count == 0
        assert on_shutdown_hook_mock.call_count == 0

    assert shutdown_mock.call_count == 1
    assert on_shutdown_hook_mock.call_count == 1


def test_multiple_lifespan_managers() -> None:
    managers = []
    startup_mocks = []
    shutdown_mocks = []

    for _ in range(10):
        startup_mock = AsyncMock()
        shutdown_mock = AsyncMock()
        managers.append(create_lifespan_manager(startup_mock, shutdown_mock))
        startup_mocks.append(startup_mock)
        shutdown_mocks.append(shutdown_mock)

    app = Speedy(lifespan=managers)
    with TestClient(app=app):
        for val in startup_mocks:
            val.assert_called_once_with(app)
        assert all(val.call_count == 0 for val in shutdown_mocks)

    assert all(val.call_count == 1 for val in startup_mocks)
    assert all(val.call_count == 1 for val in shutdown_mocks)
