from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Generic, TypeVar, Any

from speedy import BackgroundTask, BackgroundTasks, MediaType
from speedy.datastructures import Headers, MutableHeaders, Cookie
from speedy.status_code import HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_304_NOT_MODIFIED
from speedy.types import SAMESITE, ASGISendCallable, ASGIReceiveCallable, Scope

T = TypeVar('T')
ZERO_VALUE = 0


class Response(Generic[T]):
    def __init__(
            self,
            content: T | None = None,
            background: BackgroundTask | BackgroundTasks | None = None,
            headers: Headers | Mapping[str, str] | None = None,
            cookie: Sequence[Cookie] | Mapping[str, str] | None = None,
            media_type: MediaType | str | None = None,
            status_code: int | None = HTTP_200_OK,
            encoding: str = 'utf-8'
    ) -> None:
        self.background = background
        self.headers: MutableHeaders = self._init_headers(headers)
        self.media_type = media_type
        self.status_code = status_code
        self.encoding = encoding
        self.cookies = self._init_cookie(cookie)
        self.body = self.render(content)

    async def __call__(self, scope: Scope, recieve: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        prefix = 'websocket.' if scope['type'] == 'websocket' else ''
        await send(
            {
                'type': prefix + 'http.response.start',
                'status': self.status_code,
                'headers': self.headers.raw,
            }
        )
        await send({
            'type': prefix + 'http.response.body',
            'body': self.body,
        })

        if self.background is not None:
            await self.background()

    def set_cookie(
            self,
            key: str | Cookie,
            value: str = '',
            max_age: int | None = None,
            expires: datetime | str | int | None = None,
            path: str = '/',
            domain: str | None = None,
            secure: bool | None = False,
            httponly: bool | None = False,
            samesite: SAMESITE = 'lax',
    ) -> None:
        """ Set a cookie on the response. """
        if not isinstance(key, Cookie):
            key = Cookie(
                key=key,
                value=value,
                max_age=max_age,
                expires=expires,
                path=path,
                domain=domain,
                secure=secure,
                httponly=httponly,
                samesite=samesite
            )
        self.cookies.append(key)

    def delete_cookie(
            self,
            key: str,
            path: str,
            domain: str | None,
            secure: bool,
            httponly: bool,
            samesite: SAMESITE
    ) -> None:
        """ Delete a cookie. """
        cookie = Cookie(
            key=key,
            max_age=ZERO_VALUE,
            expires=ZERO_VALUE,
            path=path,
            domain=domain,
            secure=secure,
            httponly=httponly,
            samesite=samesite
        )
        self.cookies = [val for val in self.cookies if val != cookie]
        self.cookies.append(cookie)

    # TODO: add JSON processing
    def render(self, content: Any) -> bytes:
        """ Handle the rendering of content into a bytes string. """
        if content is None:
            return b''
        if isinstance(content, bytes):
            return content
        return content.encode(self.encoding)

    def set_header(self, key: str, value: Any) -> None:
        """ Set a header on the response. """
        self.headers[key] = value

    def _init_headers(self, headers: Headers | Mapping[str, str] | None) -> MutableHeaders:
        raw_headers = {}

        if isinstance(headers, Headers):
            raw_headers = {key: value for key, value in headers.items()}
        elif isinstance(headers, Mapping):
            raw_headers = dict(headers)

        keys = [key.lower() for key in raw_headers.keys()]
        is_content_length = 'content-length' in keys
        is_content_type = 'content-type' in keys

        if self.body is not None and is_content_length and not (
                self.status_code < HTTP_200_OK or self.status_code in (HTTP_204_NO_CONTENT, HTTP_304_NOT_MODIFIED)
        ):
            content_length = str(len(self.body))
            raw_headers['Content-Length'] = content_length

        content_type = self._get_content_type()
        if content_type is not None and is_content_type:
            if content_type.startswith('text/') and 'charset=' not in content_type.lower():
                content_type += f'; charset={self.encoding}'
            raw_headers['Content-Type'] = content_type
        return MutableHeaders(raw_headers)

    def _get_content_type(self) -> str | None:
        if isinstance(self.media_type, MediaType):
            return self.media_type.name
        return self.media_type

    def _init_cookie(self, cookie: Sequence[Cookie] | Mapping[str, str]) -> list[Cookie]:
        if isinstance(cookie, Mapping):
            return [Cookie(key=key, value=value) for key, value in cookie.items()]
        return list(cookie or [])
