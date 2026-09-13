from collections.abc import Callable
from typing import cast

from speedy._speedy import HTTPConnection
from speedy.authentication import AuthCredentials, AuthenticationBackend, UnauthenticatedUser
from speedy.exceptions import AuthenticationError
from speedy.responses import PlainTextResponse, Response
from speedy.status import HTTP_400_BAD_REQUEST, WS_1000_NORMAL_CLOSURE
from speedy.types import ASGIApplication, HTTPScope, Receive, Scope, Send, WebSocketScope

__all__ = ["AuthenticationMiddleware"]


class AuthenticationMiddleware:
    """Authenticate every HTTP/WebSocket connection via `backend`, attaching
    the result as `scope["auth"]`/`scope["user"]` before delegating to `app`."""

    def __init__(
        self,
        app: ASGIApplication,
        backend: AuthenticationBackend,
        on_error: Callable[[HTTPConnection, AuthenticationError], Response] | None = None,
    ) -> None:
        self.app = app
        self.backend = backend
        self.on_error: Callable[[HTTPConnection, AuthenticationError], Response] = (
            on_error if on_error is not None else self.default_on_error
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        conn_scope = cast("HTTPScope | WebSocketScope", scope)
        conn = HTTPConnection(conn_scope)
        try:
            auth_result = await self.backend.authenticate(conn)
        except AuthenticationError as exc:
            response = self.on_error(conn, exc)
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": WS_1000_NORMAL_CLOSURE, "reason": ""})
            else:
                await response(scope, receive, send)
            return

        if auth_result is None:
            auth_result = AuthCredentials(), UnauthenticatedUser()
        conn_scope["auth"], conn_scope["user"] = auth_result  # type: ignore[typeddict-unknown-key]
        await self.app(scope, receive, send)

    @staticmethod
    def default_on_error(conn: HTTPConnection, exc: Exception) -> Response:
        return PlainTextResponse(str(exc), status_code=HTTP_400_BAD_REQUEST)
