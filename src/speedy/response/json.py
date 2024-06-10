from typing import Any, Sequence, Mapping

from speedy import MediaType, BackgroundTask
from speedy.datastructures.cookie import Cookie
from speedy.exceptions import InvalidJSONLibrary
from speedy.response.base import Response
from speedy.status_code import HTTP_200_OK


class JSONResponse(Response):
    def __init__(
            self,
            content: Any | None = None,
            status_code: int = HTTP_200_OK,
            library_json: str = 'json',
            encoding: str = 'utf-8',
            cookie: Sequence[Cookie] | Mapping[str, str] | None = None,
            headers: Mapping[str, str] | None = None,
            background: BackgroundTask | None = None
    ) -> None:
        if library_json not in ('json', 'ujson', 'orjson'):
            raise InvalidJSONLibrary(
                'The following libraries are '
                'currently supported: `json`, `ujson`, `orjson`'
            )
        self._library = library_json
        super().__init__(
            content=content,
            status_code=status_code,
            encoding=encoding,
            cookie=cookie,
            headers=headers,
            media_type=MediaType.JSON,
            background=background
        )

    def render(self, content: Any | None) -> bytes:
        """
        Handle the rendering of content into a bytes string.

        Supports libraries for working with json: `json`, `orjson`, `ujson`.
        """
        return self._json_dump(content)

    def _json_dump(self, content: Any | None) -> bytes:
        if self._library == 'json':
            import json
            return json.dumps(content, ensure_ascii=False).encode('utf-8')
        elif self._library == 'ujson':
            import ujson
            return ujson.dumps(content, ensure_ascii=False).encode('utf-8')
        elif self._library == 'orjson':
            import orjson
            return orjson.dumps(content, option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY)
