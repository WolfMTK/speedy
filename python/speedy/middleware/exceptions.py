from collections.abc import Mapping
from typing import Any, cast

from speedy._exception_handler import wrap_app_handling_exceptions
from speedy.exceptions import HTTPException, WebSocketException
from speedy.requests import Request
from speedy.responses import PlainTextResponse, Response
from speedy.status import HTTP_204_NO_CONTENT, HTTP_304_NOT_MODIFIED
from speedy.types import (
    ASGIApplication,
    ExceptionHandler,
    ExceptionHandlers,
    HTTPScope,
    Receive,
    Scope,
    Send,
    StatusHandlers,
    WebSocketScope,
)
from speedy.websocket import WebSocket

__all__ = ["ExceptionMiddleware"]


class ExceptionMiddleware:
    def __init__(
        self,
        app: ASGIApplication,
        handlers: Mapping[Any, ExceptionHandler] | None = None,
        debug: bool = False,
    ) -> None:
        self.app = app
        self.debug = debug
        self._status_handlers: StatusHandlers = {}
        self._exception_handlers: ExceptionHandlers = {
            HTTPException: self.http_exception,
            WebSocketException: self.websocket_exception,
        }
        if handlers is not None:
            for key, value in handlers.items():
                self.add_exception_handler(key, value)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        scope["speedy.exception_handlers"] = (self._exception_handlers, self._status_handlers)

        conn: Request | WebSocket
        if scope["type"] == "http":
            conn = Request(cast(HTTPScope, scope), receive, send)
        else:
            conn = WebSocket(cast(WebSocketScope, scope), receive, send)

        await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)

    def add_exception_handler(
        self,
        exc_class_or_status_code: int | type[Exception],
        handler: ExceptionHandler,
    ) -> None:
        if isinstance(exc_class_or_status_code, int):
            self._status_handlers[exc_class_or_status_code] = handler
        else:
            if not issubclass(exc_class_or_status_code, Exception):
                raise TypeError(f"{exc_class_or_status_code!r} is not a subclass of Exception")
            self._exception_handlers[exc_class_or_status_code] = handler

    async def http_exception(self, request: Request, exc: Exception) -> Response:
        if not isinstance(exc, HTTPException):
            raise TypeError(f"expected HTTPException, got {type(exc).__name__}")
        if exc.status_code in {HTTP_204_NO_CONTENT, HTTP_304_NOT_MODIFIED}:
            return Response(status_code=exc.status_code, headers=exc.headers)
        return PlainTextResponse(exc.detail, status_code=exc.status_code, headers=exc.headers)

    async def websocket_exception(self, websocket: WebSocket, exc: Exception) -> None:
        if not isinstance(exc, WebSocketException):
            raise TypeError(f"expected WebSocketException, got {type(exc).__name__}")
        await websocket.close(code=exc.code, reason=exc.reason)
