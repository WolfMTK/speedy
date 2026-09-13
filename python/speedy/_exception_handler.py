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
    HTTPScope,
    Message,
    Receive,
    Scope,
    Send,
    StatusHandlers,
    WebSocketExceptionHandler,
    WebSocketScope,
)
from speedy.websocket import WebSocket


def _lookup_exception_handler(exc_handlers: ExceptionHandlers, exc: Exception) -> ExceptionHandler | None:
    for cls in type(exc).__mro__:
        if cls in exc_handlers:
            return exc_handlers[cls]
    return None


def wrap_app_handling_exceptions(app: ASGIApplication, conn: Request | WebSocket) -> ASGIApplication:
    exception_handlers, status_handlers = cast(
        "tuple[ExceptionHandlers, StatusHandlers]",
        conn.scope.get("speedy.exception_handlers", ({}, {})),
    )

    async def wrapped_app(scope: Scope, receive: Receive, send: Send) -> None:
        response_started = False

        async def sender(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

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

            if response_started:
                raise RuntimeError("Caught handled exception, but response already started.") from exc

            if scope["type"] == "http":
                http_handler = cast(HTTPExceptionHandler, handler)
                request = Request(cast(HTTPScope, scope), receive, send)
                if is_async_callable(http_handler):
                    response = cast(Response, await http_handler(request, exc))
                else:
                    response = cast(Response, await run_in_threadpool(http_handler, request, exc))
                await response(scope, receive, sender)
            else:
                websocket_handler = cast(WebSocketExceptionHandler, handler)
                websocket = WebSocket(cast(WebSocketScope, scope), receive, send)
                if is_async_callable(websocket_handler):
                    await websocket_handler(websocket, exc)
                else:
                    await run_in_threadpool(websocket_handler, websocket, exc)

    return wrapped_app
