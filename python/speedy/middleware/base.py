from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Self, cast

import anyio

from speedy.concurrency import create_collapsing_task_group
from speedy.exceptions import ClientDisconnect
from speedy.requests import Request, empty_send
from speedy.responses import Response
from speedy.types import (
    ASGIApplication,
    AsyncContentStream,
    BodyStreamGenerator,
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


class _CachedRequest(Request):
    def __new__(cls, scope: HTTPScope, receive: Receive) -> Self:
        return super().__new__(cls, scope, receive)

    def __init__(self, scope: HTTPScope, receive: Receive) -> None:
        super().__init__(scope, receive, empty_send)
        self._wrapped_rcv_disconnected = False
        self._wrapped_rcv_consumed = False
        self._wrapped_rcv_stream = self.stream()

    async def wrapped_receive(self) -> ReceiveMessage:
        if self._wrapped_rcv_disconnected:
            return {"type": "http.disconnect"}

        if self._wrapped_rcv_consumed:
            if self._is_disconnected:
                self._wrapped_rcv_disconnected = True
                return {"type": "http.disconnect"}
            msg = await self.receive()
            if msg["type"] != "http.disconnect":
                raise RuntimeError(f"Unexpected message received: {msg['type']}")
            self._wrapped_rcv_disconnected = True
            return msg

        if hasattr(self, "_body"):
            self._wrapped_rcv_consumed = True
            return {"type": "http.request", "body": self._body, "more_body": False}
        elif self._stream_consumed:
            self._wrapped_rcv_consumed = True
            return {"type": "http.request", "body": b"", "more_body": False}
        else:
            try:
                chunk = await self._wrapped_rcv_stream.__anext__()
                self._wrapped_rcv_consumed = self._stream_consumed
                return {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": not self._stream_consumed,
                }
            except ClientDisconnect:
                self._wrapped_rcv_disconnected = True
                return {"type": "http.disconnect"}


class BaseHTTPMiddleware[T]:
    def __init__(self, app: ASGIApplication, dispatch: DispatchFunction | None = None) -> None:
        self.app = app
        self.dispatch_func = self.dispatch if dispatch is None else dispatch

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        http_scope = cast(HTTPScope, scope)
        request = _CachedRequest(http_scope, receive)
        wrapped_receive = request.wrapped_receive
        response_sent = anyio.Event()
        app_exc: Exception | None = None
        exception_already_raised = False

        async def call_next(request: Request) -> Response:
            async def receive_or_disconnect() -> ReceiveMessage:
                if response_sent.is_set():
                    return {"type": "http.disconnect"}

                async with anyio.create_task_group() as task_group:

                    async def wrap[T](func: Callable[[], Awaitable[T]]) -> T:
                        result = await func()
                        task_group.cancel_scope.cancel()
                        return result

                    task_group.start_soon(wrap, response_sent.wait)
                    message = await wrap(wrapped_receive)

                if response_sent.is_set():
                    return {"type": "http.disconnect"}

                return message

            async def send_no_error(message: Message) -> None:
                try:
                    await send_stream.send(message)
                except anyio.BrokenResourceError:
                    return

                if message["type"] == "http.response.pathsend" or (
                    message["type"] == "http.response.body" and not message.get("more_body", False)
                ):
                    await response_sent.wait()

            async def coro() -> None:
                nonlocal app_exc

                with send_stream:
                    try:
                        await self.app(scope, receive_or_disconnect, send_no_error)
                    except Exception as exc:
                        app_exc = exc

            task_group.start_soon(coro)

            try:
                message = await recv_stream.receive()
                info = message.get("info", None)
                if message["type"] == "http.response.debug" and info is not None:
                    message = await recv_stream.receive()
            except anyio.EndOfStream:
                if app_exc is not None:
                    nonlocal exception_already_raised
                    exception_already_raised = True
                    raise app_exc from app_exc.__cause__ or app_exc.__context__
                raise RuntimeError("No response returned.") from None

            if message["type"] != "http.response.start":
                raise RuntimeError(f"Expected an 'http.response.start' message, got: {message['type']!r}")
            start_message = cast(HTTPResponseStartEvent, message)

            async def body_stream() -> BodyStreamGenerator:
                async for message in recv_stream:
                    if message["type"] == "http.response.pathsend":
                        yield message
                        break
                    if message["type"] != "http.response.body":
                        raise RuntimeError(f"Unexpected message: {message}")
                    body = message.get("body", b"")
                    if body:
                        yield body
                    if not message.get("more_body", False):
                        break

            response = _StreamingResponse(
                status_code=start_message["status"],
                content=body_stream(),
                info=cast("Mapping[str, Any] | None", info),
            )
            response.raw_headers = list(start_message["headers"])
            return response

        send_stream, recv_stream = anyio.create_memory_object_stream[Message]()
        with recv_stream, send_stream:
            async with create_collapsing_task_group() as task_group:
                response = await self.dispatch_func(request, call_next)
                await response(scope, wrapped_receive, send)
                response_sent.set()
                recv_stream.close()
        if app_exc is not None and not exception_already_raised:
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

        should_close_body = True
        async for chunk in self.body_iterator:
            if isinstance(chunk, dict):
                should_close_body = False
                await send(chunk)
                continue
            await send({"type": "http.response.body", "body": chunk, "more_body": True})

        if should_close_body:
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        if self.background is not None:
            await self.background()
