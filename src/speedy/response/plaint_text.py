from typing import Any, Sequence, Mapping

from speedy import MediaType, BackgroundTask
from speedy.datastructures.cookie import Cookie
from speedy.protocols.response import AbstractMediaTypeResponse
from speedy.response.base import Response
from speedy.status_code import HTTP_200_OK


class PlainTextResponse(AbstractMediaTypeResponse, Response):
    def __init__(
            self,
            content: Any | None = None,
            status_code: int = HTTP_200_OK,
            encoding: str = 'utf-8',
            cookie: Sequence[Cookie] | Mapping[str, str] | None = None,
            headers: Mapping[str, str] | None = None,
            background: BackgroundTask | None = None
    ) -> None:
        super().__init__(
            content=content,
            status_code=status_code,
            encoding=encoding,
            cookie=cookie,
            headers=headers,
            media_type=MediaType.TEXT,
            background=background
        )
