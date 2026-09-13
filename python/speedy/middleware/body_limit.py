from typing import cast

from speedy.datastructures import Headers
from speedy.exceptions import ApplicationException, HTTPException
from speedy.responses import PlainTextResponse
from speedy.status import HTTP_413_CONTENT_TOO_LARGE
from speedy.types import ASGIApplication, Message, Receive, ReceiveMessage, Scope, Send

__all__ = ["RequestBodyLimitMiddleware", "RequestBodyLimitResponder"]

MAX_BODY_SIZE_SCOPE_KEY = "speedy.max_body_size"
_BODY_LIMIT_RESPONDER_SCOPE_KEY = "speedy._body_limit_responder"


class _Missing:
    __slots__ = ()


_MISSING = _Missing()


class _RequestBodyTooLarge(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=HTTP_413_CONTENT_TOO_LARGE, detail="Content Too Large")


class _RequestBodyLimitResponseSent(ApplicationException):
    pass


class RequestBodyLimitMiddleware:
    """Limit the total size of an HTTP request body."""

    def __init__(self, app: ASGIApplication, max_body_size: int) -> None:
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        responder = RequestBodyLimitResponder(self.app, self.max_body_size)
        await responder(scope, receive, send)


class RequestBodyLimitResponder:
    def __init__(self, app: ASGIApplication, max_body_size: int) -> None:
        self.app = app
        self.max_body_size = max_body_size
        self._scope: Scope | None = None
        self._receive: Receive | None = None
        self._send: Send | None = None
        self.content_length: int | None = None
        self.total_size = 0
        self.response_started = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        previous_scope_limit = cast("int | _Missing", scope.get(MAX_BODY_SIZE_SCOPE_KEY, _MISSING))
        scope[MAX_BODY_SIZE_SCOPE_KEY] = self.max_body_size

        active_responder = cast(
            "RequestBodyLimitResponder | None",
            scope.get(_BODY_LIMIT_RESPONDER_SCOPE_KEY),
        )
        if active_responder is not None:
            active_responder.max_body_size = self.max_body_size
            if active_responder.total_size > active_responder.max_body_size:
                raise _RequestBodyTooLarge
            return await self.app(scope, receive, send)

        self._scope = scope
        self._receive = receive
        self._send = send
        self.content_length = _get_content_length(scope)
        scope[_BODY_LIMIT_RESPONDER_SCOPE_KEY] = self

        try:
            await self.app(scope, self.receive_with_limit, self.send_with_limit)
        except _RequestBodyTooLarge:
            if self.response_started:
                raise
            response = PlainTextResponse("Content Too Large", status_code=HTTP_413_CONTENT_TOO_LARGE)
            await response(scope, receive, send)
        except _RequestBodyLimitResponseSent:
            pass
        finally:
            scope.pop(_BODY_LIMIT_RESPONDER_SCOPE_KEY, None)
            if isinstance(previous_scope_limit, _Missing):
                scope.pop(MAX_BODY_SIZE_SCOPE_KEY, None)
            else:
                scope[MAX_BODY_SIZE_SCOPE_KEY] = previous_scope_limit

    @property
    def scope(self) -> Scope:
        if self._scope is None:
            raise RuntimeError("scope accessed before RequestBodyLimitResponder.__call__ ran")
        return self._scope

    @property
    def receive(self) -> Receive:
        if self._receive is None:
            raise RuntimeError("receive accessed before RequestBodyLimitResponder.__call__ ran")
        return self._receive

    @property
    def send(self) -> Send:
        if self._send is None:
            raise RuntimeError("send accessed before RequestBodyLimitResponder.__call__ ran")
        return self._send

    async def receive_with_limit(self) -> ReceiveMessage:
        if self.content_length is not None and self.content_length > self.max_body_size:
            raise _RequestBodyTooLarge

        message = await self.receive()
        if message["type"] == "http.request":
            self.total_size += len(message.get("body", b""))
            if self.total_size > self.max_body_size:
                raise _RequestBodyTooLarge
        return message

    async def send_with_limit(self, message: Message) -> None:
        if message["type"] == "http.response.start":
            self.response_started = True
            if self.content_length is not None and self.content_length > self.max_body_size:
                response = PlainTextResponse("Content Too Large", status_code=HTTP_413_CONTENT_TOO_LARGE)
                await response(self.scope, self.receive, self.send)
                raise _RequestBodyLimitResponseSent
        await self.send(message)


def _get_content_length(scope: Scope) -> int | None:
    content_length = Headers(scope=scope).get("content-length")
    if content_length is None:
        return None
    try:
        parsed = int(content_length)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None
