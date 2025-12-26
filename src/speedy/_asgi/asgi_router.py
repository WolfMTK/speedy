from __future__ import annotations

from traceback import format_exc
from typing import TYPE_CHECKING

from speedy.types import (
    LifeSpanReceive,
    LifeSpanSend,
    LifespanShutdownCompleteEvent,
    LifespanStartupCompleteEvent,
    LifespanStartupFailedEvent,
    LifespanShutdownFailedEvent,
)

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
        started = False
        try:
            async with self.app.lifespan():
                await send(startup_event)
                started = True
                await receive()
        except BaseException as e:
            formatted_exception = format_exc()

            if started:
                fail_message: LifespanShutdownFailedEvent = {
                    "type": "lifespan.shutdown.failed",
                    "message": formatted_exception,
                }
            else:
                fail_message: LifespanStartupFailedEvent = {
                    "type": "lifespan.startup.failed",
                    "message": formatted_exception,
                }

            await send(fail_message)
            raise e

        await send(shutdown_event)
