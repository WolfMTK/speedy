from typing import Any

from speedy.enums import MediaTextType
from speedy.protocols.background import AbstractBackground
from speedy.response.base import ASGIResponse
from speedy.status_code import HTTP_200_OK


class PlainTextResponse(ASGIResponse):
    """ Response class with plain text passing. """

    def __init__(
            self,
            content: Any = None,
            status_code: int = HTTP_200_OK,
            headers: dict[str, str] | None = None,
            charset: str | None = None,
            background: None | AbstractBackground = None
    ) -> None:
        media_type = MediaTextType.PLAIN
        super().__init__(content, status_code, headers, charset, media_type, background)
