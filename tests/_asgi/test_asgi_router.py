from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Callable, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, call

import anyio
import pytest
from pytest_mock import MockerFixture

from speedy import Speedy
from speedy._asgi import ASGIRouter
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


@pytest.fixture
def mock_format_exc(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("speedy._asgi.asgi_router.format_exc")


async def test_lifespan_startup_fail(mock_format_exc: MagicMock) -> None:
    receive = AsyncMock()
    receive.return_value = {"type": "lifespan.startup"}
    send = AsyncMock()
    exception = ValueError("foo")
    mock_format_exc.return_value = str(exception)

    mock_on_startup = AsyncMock(side_effect=exception)

    async def on_startup() -> None:
        await mock_on_startup()

    router = ASGIRouter(app=Speedy(on_startup=[on_startup]))

    with pytest.raises(ValueError, match="foo"):
        await router.lifespan(receive, send)

    assert send.call_count == 1
    send.assert_called_once_with({"type": "lifespan.startup.failed", "message": mock_format_exc.return_value})


async def test_lifespan_shutdown_fail(mock_format_exc: MagicMock) -> None:
    receive = AsyncMock()
    receive.return_value = {"type": "lifespan.shutdown"}
    send = AsyncMock()
    exception = ValueError("foo")
    mock_format_exc.return_value = str(exception)

    mock_on_shutdown = AsyncMock(side_effect=exception)

    async def on_shutdown() -> None:
        await mock_on_shutdown()

    router = ASGIRouter(app=Speedy(on_shutdown=[on_shutdown]))

    with pytest.raises(ValueError, match="foo"):
        await router.lifespan(receive, send)

    assert send.call_count == 2
    assert send.call_args_list[1][0][0] == {"type": "lifespan.shutdown.failed", "message": mock_format_exc.return_value}


async def test_lifespan_context_exception_after_startup(mock_format_exc: MagicMock) -> None:
    receive = AsyncMock()
    receive.return_value = {"type": "lifespan.startup"}
    send = AsyncMock()
    mock_format_exc.return_value = "foo"

    async def sleep_and_raise() -> None:
        await anyio.sleep(0)
        raise ValueError("error")

    @asynccontextmanager
    async def lifespan(_: Speedy) -> AsyncGenerator[None, None]:
        async with anyio.create_task_group() as tg:
            tg.start_soon(sleep_and_raise)
            yield

    router = ASGIRouter(app=Speedy(lifespan=[lifespan]))

    with pytest.RaisesGroup(pytest.RaisesExc(ValueError, match="error"), flatten_subgroups=True):
        await router.lifespan(receive, send)

    assert receive.call_count == 2
    send.assert_has_calls(
        [
            call({"type": "lifespan.startup.complete"}),
            call({"type": "lifespan.shutdown.failed", "message": mock_format_exc.return_value}),
        ]
    )
