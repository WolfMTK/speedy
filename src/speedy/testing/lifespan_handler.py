from __future__ import annotations

import contextlib
from math import inf
from types import TracebackType
from typing import Optional, Self

import anyio
from anyio import create_memory_object_stream
from anyio.streams.stapled import StapledObjectStream

from speedy.types import (
    ASGIApp,
    LifespanStartupEvent,
    LifeSpanSendMessage,
    LifespanShutdownEvent,
    LifeSpanReceiveMessage,
)


class LifeSpanHandler:
    def __init__(self, app: ASGIApp) -> None:
        self.stream_send = StapledObjectStream[Optional["LifeSpanSendMessage"]](
            *create_memory_object_stream(inf),
        )
        self.stream_receive = StapledObjectStream["LifeSpanReceiveMessage"](
            *create_memory_object_stream(inf),
        )
        self.app = app
        self._exit_stack = contextlib.AsyncExitStack()

    async def __aenter__(self) -> Self:
        async with contextlib.AsyncExitStack() as exit_stack:
            await exit_stack.enter_async_context(self.stream_send)
            await exit_stack.enter_async_context(self.stream_receive)

            self._tg = await exit_stack.enter_async_context(anyio.create_task_group())
            with anyio.CancelScope() as cs:
                self._tg.start_soon(self.lifespan, cs)
                await self.wait_startup()
            exit_stack.push_async_callback(self.wait_shutdown)
            self._exit_stack = exit_stack.pop_all()
        return self

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
    ) -> None:
        await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)

    async def wait_startup(self) -> None:
        event: LifespanStartupEvent = {"type": "lifespan.startup"}
        await self.stream_receive.send(event)

        message = await self.receive()
        if message["type"] not in (
                "lifespan.startup.complete",
                "lifespan.startup.failed",
        ):
            raise RuntimeError(
                "Received unexpected ASGI message type. Expected `lifespan.startup.complete` or "
                f"`lifespan.startup.failed`. Got {message['type']!r}",
            )
        if message["type"] == "lifespan.startup.failed":
            await self.receive()

    async def wait_shutdown(self) -> None:
        event: LifespanShutdownEvent = {"type": "lifespan.shutdown"}
        await self.stream_receive.send(event)

        message = await self.receive()
        if message["type"] not in (
                "lifespan.shutdown.complete",
                "lifespan.shutdown.failed",
        ):
            raise RuntimeError(
                "Received unexpected ASGI message type. Expected 'lifespan.shutdown.complete' or "
                f"'lifespan.shutdown.failed'. Got {message['type']!r}",
            )
        if message["type"] == "lifespan.shutdown.failed":
            await self.receive()

    async def receive(self) -> LifeSpanSendMessage:
        message = await self.stream_send.receive()
        return message

    async def lifespan(self, cs: anyio.CancelScope) -> None:
        scope = {"type": "lifespan"}
        try:
            await self.app(scope, self.stream_receive.receive, self.stream_send.send)  # noqa
        except BaseException:
            cs.cancel()
            raise
