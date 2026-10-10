import asyncio
from collections import deque
from collections.abc import AsyncIterator, Mapping
from typing import Any, Self, cast

from speedy.concurrency import create_collapsing_task_group
from speedy.exceptions import ClientDisconnect
from speedy.requests import Request, empty_send
from speedy.responses import Response
from speedy.types import (
    ASGIApplication,
    AsyncContentStream,
    DispatchFunction,
    HTTPResponseStartEvent,
    HTTPScope,
    Message,
    Receive,
    ReceiveMessage,
    RequestResponseEndpoint,
    Scope,
    Send,
)


def _disconnect() -> ReceiveMessage:
    return {"type": "http.disconnect"}


class _ChannelClosed(Exception):
    pass


class _Channel:
    __slots__ = ("_aborted", "_buf", "_cap", "_closed", "_waiter")

    def __init__(self, capacity: int = 1) -> None:
        self._buf: deque[Message] = deque()
        self._cap = capacity
        self._waiter: asyncio.Future[None] | None = None
        self._closed = False
        self._aborted = False

    def _wake(self) -> None:
        waiter, self._waiter = self._waiter, None
        if waiter is not None and not waiter.done():
            waiter.set_result(None)

    async def put(self, item: Message) -> None:
        while len(self._buf) >= self._cap:
            if self._aborted:
                raise _ChannelClosed
            self._waiter = asyncio.get_running_loop().create_future()
            await self._waiter
        if self._aborted or self._closed:
            raise _ChannelClosed
        self._buf.append(item)
        self._wake()

    async def get(self) -> Message:
        while not self._buf:
            if self._closed or self._aborted:
                raise _ChannelClosed
            self._waiter = asyncio.get_running_loop().create_future()
            await self._waiter
        item = self._buf.popleft()
        self._wake()
        return item

    def close(self) -> None:
        self._closed = True
        self._wake()

    def abort(self) -> None:
        self._aborted = True
        self._buf.clear()
        self._wake()


async def _get_or_none(channel: _Channel) -> Message | None:
    try:
        return await channel.get()
    except _ChannelClosed:
        return None


async def _first_done(a: asyncio.Future[Any], b: asyncio.Future[Any]) -> None:
    if a.done() or b.done():
        return
    waiter: asyncio.Future[None] = asyncio.get_running_loop().create_future()

    def _on_done(_: object) -> None:
        if not waiter.done():
            waiter.set_result(None)

    a.add_done_callback(_on_done)
    b.add_done_callback(_on_done)
    try:
        await waiter
    finally:
        a.remove_done_callback(_on_done)
        b.remove_done_callback(_on_done)


class _CachedRequest(Request):
    def __new__(cls, scope: HTTPScope, receive: Receive) -> Self:
        return super().__new__(cls, scope, receive)

    def __init__(self, scope: HTTPScope, receive: Receive) -> None:
        super().__init__(scope, receive, empty_send)
        self._replay_stream = self.stream()
        self._body_replayed = False
        self._disconnect_sent = False
        self._inflight: asyncio.Task[ReceiveMessage] | None = None
        self._lock = asyncio.Lock()

    async def _replay(self) -> ReceiveMessage:
        if self._disconnect_sent:
            return _disconnect()

        if self._body_replayed:
            if self._is_disconnected:
                self._disconnect_sent = True
                return _disconnect()
            msg = await self.receive()
            if msg["type"] != "http.disconnect":
                raise RuntimeError(f"Unexpected ASGI message: {msg['type']}")
            self._disconnect_sent = True
            return msg

        body = getattr(self, "_body", None)
        if body is not None:
            self._body_replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        if self._stream_consumed:
            self._body_replayed = True
            return {"type": "http.request", "body": b"", "more_body": False}

        try:
            chunk = await self._replay_stream.__anext__()
        except StopAsyncIteration:
            self._body_replayed = True
            return {"type": "http.request", "body": b"", "more_body": False}
        except ClientDisconnect:
            self._disconnect_sent = True
            return _disconnect()

        self._body_replayed = self._stream_consumed
        return {"type": "http.request", "body": chunk, "more_body": not self._stream_consumed}

    async def receive_message(self, stop: asyncio.Future[Any] | None = None) -> ReceiveMessage:
        async with self._lock:
            task = self._inflight
            if task is None:
                task = self._inflight = asyncio.get_running_loop().create_task(self._replay())

            if stop is None:
                await asyncio.shield(task)
            else:
                await _first_done(task, stop)
                if not task.done():
                    return _disconnect()

            self._inflight = None
            return task.result()

    async def aclose(self) -> None:
        task, self._inflight = self._inflight, None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.wait((task,))
        if task is not None and not task.cancelled():
            task.exception()
        await self._replay_stream.aclose()


class BaseHTTPMiddleware[T]:
    __slots__ = ("app", "dispatch_func")

    def __init__(self, app: ASGIApplication, dispatch: DispatchFunction | None = None) -> None:
        self.app = app
        self.dispatch_func = self.dispatch if dispatch is None else dispatch

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = _CachedRequest(cast(HTTPScope, scope), receive)
        response_done: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        channel = _Channel()
        app_exc: Exception | None = None
        app_started = False
        exc_reported = False

        async def downstream_receive() -> ReceiveMessage:
            if response_done.done():
                return _disconnect()
            return await request.receive_message(stop=response_done)

        async def downstream_send(message: Message) -> None:
            if response_done.done():
                return
            try:
                await channel.put(message)
            except _ChannelClosed:
                return
            if message["type"] == "http.response.pathsend" or (
                message["type"] == "http.response.body" and not message.get("more_body", False)
            ):
                await response_done

        async def run_app() -> None:
            nonlocal app_exc
            try:
                await self.app(scope, downstream_receive, downstream_send)
            except Exception as exc:
                app_exc = exc
            finally:
                channel.close()

        async def call_next(req: Request) -> Response:
            nonlocal app_started, exc_reported
            if req is not request:
                raise ValueError("call_next() must receive the same request passed to dispatch()")
            if app_started:
                raise RuntimeError("call_next() may only be called once")
            app_started = True
            task_group.create_task(run_app())

            info: Mapping[str, Any] | None = None
            while True:
                message = await _get_or_none(channel)
                if message is None:
                    if app_exc is not None:
                        exc_reported = True
                        raise app_exc
                    raise RuntimeError("Application finished without sending a response")
                if message["type"] != "http.response.debug":
                    break
                info = message.get("info", info)

            if message["type"] != "http.response.start":
                raise RuntimeError(f"Expected 'http.response.start', got: {message['type']!r}")
            start = cast(HTTPResponseStartEvent, message)

            async def body_stream() -> AsyncIterator[bytes | Message]:
                nonlocal exc_reported
                while True:
                    msg = await _get_or_none(channel)
                    if msg is None:
                        if app_exc is not None:
                            exc_reported = True
                            raise app_exc
                        return

                    mtype = msg["type"]
                    if mtype == "http.response.debug":
                        continue
                    if mtype == "http.response.pathsend":
                        yield msg
                        return
                    if mtype != "http.response.body":
                        raise RuntimeError(f"Unexpected message from application: {mtype!r}")

                    body = msg.get("body", b"")
                    if body:
                        yield body
                    if not msg.get("more_body", False):
                        return

            response = _StreamingResponse(
                status_code=start["status"],
                content=body_stream(),
                info=info,
            )
            response.raw_headers = list(start["headers"])
            return response

        try:
            async with create_collapsing_task_group() as task_group:
                try:
                    response = await self.dispatch_func(request, call_next)
                    await response(scope, request.receive_message, send)
                finally:
                    if not response_done.done():
                        response_done.set_result(None)
                    channel.abort()
        finally:
            await request.aclose()

        if app_exc is not None and not exc_reported:
            raise app_exc

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raise NotImplementedError


class _StreamingResponse(Response):
    def __new__(
        cls,
        content: AsyncContentStream,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        info: Mapping[str, Any] | None = None,
    ) -> Self:
        return super().__new__(cls, b"", status_code, headers, media_type, None)

    def __init__(
        self,
        content: AsyncContentStream,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        info: Mapping[str, Any] | None = None,
    ) -> None:
        if "content-length" in self.headers:
            del self.headers["content-length"]
        self.info = info
        self.body_iterator = content

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.info is not None:
            await send({"type": "http.response.debug", "info": self.info})
        await send({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})

        close_body = True
        async for chunk in self.body_iterator:
            if isinstance(chunk, dict):
                close_body = False
                await send(chunk)
            else:
                await send({"type": "http.response.body", "body": chunk, "more_body": True})

        if close_body:
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        if self.background is not None:
            await self.background()
