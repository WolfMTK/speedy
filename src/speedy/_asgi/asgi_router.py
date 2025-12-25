from __future__ import annotations

from traceback import format_exc
from typing import TYPE_CHECKING

from speedy.types import (
    Scope,
    Receive,
    Send,
    LifeSpanReceive,
    LifeSpanSend,
    LifespanShutdownCompleteEvent,
    LifespanStartupCompleteEvent,
    LifespanShutdownFailedEvent,
    LifespanStartupFailedEvent,
)

if TYPE_CHECKING:
    from speedy import Speedy


class ASGIRouter:
    """ Speedy ASGI router. """

    def __init__(self, app: Speedy) -> None:
        self.app = app

    async def __call__(
            self,
            scope: Scope,
            receive: Receive,
            send: Send,
    ) -> None:
        ...

    async def lifespan(
            self,
            receive: LifeSpanReceive,
            send: LifeSpanSend,
    ) -> None:
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
        except BaseException as err:
            await self._send_failed_message(send, started)
            raise err

        await send(shutdown_event)

    async def _send_failed_message(
            self,
            send: LifeSpanSend,
            started: bool,
    ) -> None:
        formatted_exception = format_exc()
        if started:
            failed_message: LifespanShutdownFailedEvent = {
                "type": "lifespan.shutdown.failed",
                "message": formatted_exception,
            }
        else:
            failed_message: LifespanStartupFailedEvent = {
                "type": "lifespan.startup.failed",
                "message": formatted_exception,
            }

        await send(failed_message)
