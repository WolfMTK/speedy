from datetime import datetime
from typing import Any, Mapping, overload, Sequence, Generator

from speedy import BackgroundTask, MediaType, ScopeType
from speedy.datastructures import MutableHeaders
from speedy.datastructures.cookie import Cookie
from speedy.protocols.response import AbstractResponse
from speedy.status_code import HTTP_200_OK, HTTP_204_NO_CONTENT
from speedy.types import SAMESITE, Scope, ASGIReceiveCallable, ASGISendCallable

ZERO_VALUE = 0


class Response(AbstractResponse):
    """ Base response class. """

    _raw_header: list[tuple[bytes, bytes]]

    def __init__(
            self,
            content: Any | None = None,
            status_code: int = HTTP_200_OK,
            encoding: str = 'utf-8',
            cookie: Sequence[Cookie] | Mapping[str, str] | None = None,
            headers: Mapping[str, str] | None = None,
            media_type: MediaType | str | None = None,
            background: BackgroundTask | None = None
    ) -> None:
        self.background = background
        self.media_type = media_type
        self.encoding = encoding
        self.cookies = self._init_cookie(cookie)
        self.status_code = status_code
        self.body = self.render(content)
        self.init_headers(headers)

    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        prefix = 'websocket.' if scope['type'] == ScopeType.WEBSOCKET else ''

        await self.start_response(prefix, send)
        await self.send_body(prefix, send, receive)
        if self.background is not None:
            await self.background()

    @property
    def raw_header(self) -> list[tuple[bytes, bytes]]:
        """ Get the raw headers. """
        return self._raw_header + [*self._encode_cookies()]

    @property
    def headers(self) -> MutableHeaders:
        """ Get the headers. """
        if not hasattr(self, '_headers'):
            self._headers = MutableHeaders(self.raw_header)
        return self._headers

    @overload
    def set_cookie(self, /, cookie: Cookie) -> None:
        ...

    @overload
    def set_cookie(
            self,
            key: str,
            value: str | None = None,
            max_age: int | None = None,
            expires: datetime | str | int | None = None,
            path: str = '/',
            domain: str | None = None,
            secure: bool = False,
            httponly: bool = False,
            samesite: SAMESITE = 'lax'
    ) -> None:
        ...

    def set_cookie(
            self,
            key: str | Cookie,
            value: str | None = None,
            max_age: int | None = None,
            expires: datetime | str | int | None = None,
            path: str = '/',
            domain: str | None = None,
            secure: bool = False,
            httponly: bool = False,
            samesite: SAMESITE = 'lax'
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

    async def start_response(self, prefix: str, send: ASGISendCallable) -> None:
        """ Emit the start event of the response. """
        await send(
            {
                'type': prefix + 'http.response.start',
                'status': self.status_code,
                'headers': self.raw_header
            }
        )

    async def send_body(self, prefix: str, send: ASGISendCallable, receive: ASGIReceiveCallable) -> None:
        """ Emit the response body. """
        await send(
            {
                'type': prefix + 'http.response.body',
                'body': self.body
            }
        )

    def render(self, content: Any | None) -> bytes:
        """ Handle the rendering of content into a bytes string. """
        if content is None:
            return b''
        if isinstance(content, bytes):
            return content
        return content.encode(self.encoding)  # type: ignore

    def init_headers(self, headers: Mapping[str, str] | None = None) -> None:
        """ Initializing headers and adding them to the common scope. """
        raw_headers = self._to_raw_headers(headers)
        self._set_content_length(raw_headers)
        self._set_content_type(raw_headers)
        self._raw_header = raw_headers

    def _set_content_length(self, raw_headers: list[tuple[bytes, bytes]]) -> None:
        is_content_length = self._is_content_length(raw_headers)
        is_status = self.status_code < HTTP_200_OK or self.status_code in (HTTP_204_NO_CONTENT, HTTP_204_NO_CONTENT)
        body = getattr(self, 'body', None)

        if body is not None and is_content_length and not is_status:
            content_length = str(len(body))
            raw_headers.append((b'content_length', content_length.encode('latin-1')))

    def _set_content_type(self, raw_headers: list[tuple[bytes, bytes]]) -> None:
        is_content_type = self._is_content_type(raw_headers)
        content_type = self.media_type
        if content_type is not None and is_content_type:
            if content_type.startswith('text/') and 'charset=' not in content_type.lower():
                content_type += '; charset=' + self.encoding
            raw_headers.append((b'content-type', content_type.encode('latin-1')))

    def _is_content_length(self, raw_headers: list[tuple[bytes, bytes]]) -> bool:
        if len(raw_headers) == ZERO_VALUE:
            return True
        keys = [header[0] for header in raw_headers]
        return b'content-length' not in keys

    def _is_content_type(self, raw_headers: list[tuple[bytes, bytes]]) -> bool:
        if len(raw_headers) == ZERO_VALUE:
            return True
        keys = [header[0] for header in raw_headers]
        return b'content-type' not in keys

    def _to_raw_headers(self, headers: Mapping[str, str] | None = None) -> list[tuple[bytes, bytes]]:
        if headers is None:
            return []
        return [
            (key.lower().encode('latin-1'), value.encode('latin-1'))
            for key, value in headers.items()
        ]

    def _init_cookie(self, cookie: Sequence[Cookie] | Mapping[str, str]) -> list[Cookie]:
        if isinstance(cookie, Mapping):
            return [Cookie(key=key, value=value) for key, value in cookie.items()]
        return list(cookie or [])

    def _encode_cookies(self) -> Generator[tuple[bytes, bytes], Any, None]:
        if len(self.cookies) == ZERO_VALUE:
            yield ()
            return

        for cookie in self.cookies:
            yield cookie.to_encoded_header()
