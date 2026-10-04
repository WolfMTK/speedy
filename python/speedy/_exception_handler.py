from collections.abc import Callable
from typing import cast

from speedy.concurrency import is_async_callable, run_in_threadpool
from speedy.exceptions import HTTPException
from speedy.requests import Request
from speedy.responses import Response
from speedy.types import (
    ASGIApplication,
    ExceptionHandler,
    ExceptionHandlers,
    HTTPExceptionHandler,
    Message,
    Receive,
    Scope,
    Send,
    StatusHandlers,
    WebSocketExceptionHandler,
)
from speedy.websocket import WebSocket


class ResponseTracker:
    __slots__ = (
        "_send",
        "started",
    )

    def __init__(self, send: Send) -> None:
        self._send = send
        self.started = False

    async def __call__(self, message: Message) -> None:
        if message["type"] == "http.response.start":
            self.started = True
        await self._send(message)


def track_response(send: Send) -> ResponseTracker:
    if type(send) is ResponseTracker and not send.started:
        return send
    return ResponseTracker(send)


def _lookup_exception_handler(exc_handlers: ExceptionHandlers, exc: Exception) -> ExceptionHandler | None:
    for cls in type(exc).__mro__:
        if cls in exc_handlers:
            return exc_handlers[cls]
    return None


def wrap_app_handling_exceptions(
    app: ASGIApplication, scope: Scope, get_conn: Callable[[], Request | WebSocket]
) -> ASGIApplication:
    exception_handlers, status_handlers = cast(
        "tuple[ExceptionHandlers, StatusHandlers]",
        scope.get("speedy.exception_handlers", ({}, {})),
    )

    async def wrapped_app(scope: Scope, receive: Receive, send: Send) -> None:
        sender = track_response(send)
        try:
            await app(scope, receive, sender)
        except Exception as exc:
            handler = None

            if isinstance(exc, HTTPException):
                handler = status_handlers.get(exc.status_code)

            if handler is None:
                handler = _lookup_exception_handler(exception_handlers, exc)

            if handler is None:
                raise

            if sender.started:
                raise RuntimeError("Caught handled exception, but response already started.") from exc

            if scope["type"] == "http":
                http_handler = cast(HTTPExceptionHandler, handler)
                request = cast(Request, get_conn())
                if is_async_callable(http_handler):
                    response = cast(Response, await http_handler(request, exc))
                else:
                    response = cast(Response, await run_in_threadpool(http_handler, request, exc))
                await response(scope, receive, sender)
            else:
                websocket_handler = cast(WebSocketExceptionHandler, handler)
                websocket = cast(WebSocket, get_conn())
                if is_async_callable(websocket_handler):
                    ws_response = cast("Response | None", await websocket_handler(websocket, exc))
                else:
                    ws_response = cast("Response | None", await run_in_threadpool(websocket_handler, websocket, exc))
                if ws_response is not None:
                    await ws_response(scope, receive, sender)

    return wrapped_app
