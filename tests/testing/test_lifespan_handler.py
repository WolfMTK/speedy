import pytest

from speedy.testing.lifespan_handler import LifeSpanHandler
from speedy.types import Scope, Receive, Send

pytestmark = pytest.mark.filterwarnings("default")


async def test_wait_startup_invalid_event() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "lifespan.startup.something_unexpected"})  # type: ignore[typeddict-item]

    with pytest.RaisesGroup(pytest.RaisesExc(RuntimeError, match="Received unexpected ASGI message type")):
        async with LifeSpanHandler(app):
            pass


async def test_wait_shutdown_invalid_event() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "lifespan.startup.complete"}) # noqa
        await send({"type": "lifespan.shutdown.something_unexpected"}) # noqa

    with pytest.RaisesGroup(pytest.RaisesExc(RuntimeError, match="Received unexpected ASGI message type")):
        async with LifeSpanHandler(app):
            pass
