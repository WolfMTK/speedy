from typing import Any

from speedy.protocols import AbstractResponse
from speedy.protocols.background import AbstractBackground
from speedy.status_code import HTTP_200_OK
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable


class ASGIResponse(AbstractResponse):
    """ Base ASGI response class. """

    def __init__(
            self,
            content: Any = None,
            status_code: int = HTTP_200_OK,
            headers: dict[str, str] | None = None,
            charset: str | None = None,
            media_type: str | None = None,
            background: None | AbstractBackground = None
    ):
        super().__init__(content, status_code, headers, media_type, background)
        if charset is None:
            charset = 'utf-8'
        self.charset = charset
        self.body = self.render(content)
        self.raw_headers: list[Any] = []

    def render(self, content: Any) -> bytes:
        if content is None:
            return b''
        if isinstance(content, bytes):
            return content
        return content.encode(self.charset)  # type: ignore

    async def __call__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable,
            send: ASGISendCallable
    ) -> None:
        # TODO: Replace with structures
        # prefix = 'websocket.' if scope['type'] == 'websocket' else ''
        # await send(
        #     {
        #         'type': prefix + 'http.response.start',
        #         'status': self.status_code,
        #         'headers': self.raw_headers
        #     }
        # )
        # await send(
        #     {
        #         'type': prefix + 'http.response.start',
        #         'body': self.body
        #     }
        # )
        ...
