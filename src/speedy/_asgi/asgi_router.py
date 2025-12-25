from __future__ import annotations

from typing import TYPE_CHECKING

from speedy.types import LifeSpanReceive, LifeSpanSend, LifespanShutdownCompleteEvent, LifespanStartupCompleteEvent

if TYPE_CHECKING:
    from speedy import Speedy


class ASGIRouter:
    """ Speedy ASGI router. """

    def __init__(self, app: Speedy) -> None:
        self.app = app

    async def lifespan(self, receive: LifeSpanReceive, send: LifeSpanSend) -> None:
        """ Handle the ASGI `lifespan` event on application startup and shutdown. """
        startup_event: LifespanStartupCompleteEvent = {"type": "lifespan.startup.complete"}
        shutdown_event: LifespanShutdownCompleteEvent = {"type": "lifespan.shutdown.complete"}

        await receive()
        async with self.app.lifespan():
            await send(startup_event)
            await receive()

        await send(shutdown_event)
