from typing import Any, Self

from speedy._speedy import Response as _Response
from speedy.types import Message, Receive, Scope, Send

__all__ = ["Response"]


class Response(_Response):
    def _wrap_websocket_denial_send(self, send: Send) -> Send:
        async def wrapped(message: Message) -> None:
            message_type = message["type"]
            if message_type in {"http.response.start", "http.response.body"}:  # pragma: no branch
                message = {**message, "type": "websocket." + message_type}
            await send(message)

        return wrapped

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            send = self._wrap_websocket_denial_send(send)

        await send({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})
        await send({"type": "http.response.body", "body": self.body})

        if self.background is not None:
            await self.background()


class PlaintTextResponse(Response):
    def __new__(
        cls,
        content: Any = None,
        status_code: int = 200,
        headers: Any = None,
        media_type: str | None = "text/plain",
        background: Any = None,
    ) -> Self:
        return super().__new__(cls, content, status_code, headers, media_type, background)
