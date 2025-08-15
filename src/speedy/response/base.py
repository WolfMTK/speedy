from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import TypeVar, Any, ClassVar, Generic

from speedy import BackgroundTask, BackgroundTasks, MediaType
from speedy.datastructures import MutableHeaders, Cookie, Headers
from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.status_code import HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_304_NOT_MODIFIED
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable, SAMESITE
from speedy.types.asgi_types import HTTPResponseStartEvent, HTTPResponseBodyEvent
from speedy.utils.helpers import get_enum_string_value

T = TypeVar('T')
ZERO_VALUE = 0


class ASGIResponse:
    """ A low-level ASGI response class. """

    _should_set_content_length: ClassVar[bool] = True

    def __init__(
            self,
            background: BackgroundTask | BackgroundTasks | None = None,
            body: bytes | str = b"",
            content_length: int | None = None,
            cookies: Iterable[Cookie] | None = None,
            encoding: str = "utf-8",
            headers: dict[str, Any] | Iterable[tuple[str, str]] | None = None,
            is_head_response: bool = False,
            media_type: MediaType | str | None = None,
            status_code: int | None = None,
    ) -> None:
        body = body.encode() if isinstance(body, str) else body
        status_code = status_code or HTTP_200_OK
        self.headers = MutableHeaders(headers)
        self._set_headers(headers)
        media_type = get_enum_string_value(media_type or MediaType.JSON)
        status_allows_body = (
                status_code not in (HTTP_204_NO_CONTENT, HTTP_304_NOT_MODIFIED) and status_code >= HTTP_200_OK
        )
        content_length = self._get_content_length(body, content_length)

        if not status_allows_body or is_head_response:
            self._check_body(body)
            body = b""
        else:
            self._set_content_type(encoding, media_type)
            self._set_content_length(content_length)

        self.background = background
        self.body = body
        self._encoded_cookies = self._get_encoded_cookies(cookies)
        self.encoding = encoding
        self.is_head_response = is_head_response
        self.status_code: int = status_code

    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        await self.start_response(send)

        if self.is_head_response:
            event: HTTPResponseBodyEvent = {
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            }
            await send(event)
        else:
            await self.send_body(send, receive)

        await self.after_response()

    def encode_headers(self) -> list[tuple[bytes, bytes]]:
        """ Encode headers. """
        return [*self.headers.raw, *self._encoded_cookies]

    async def after_response(self) -> None:
        """ Execute after the response is sent. """
        if self.background is not None:
            await self.background()

    async def start_response(self, send: ASGISendCallable) -> None:
        """ Emit the start event of the response. This event includes the headers and status codes. """
        event: HTTPResponseStartEvent = {
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self.encode_headers(),
        }
        await send(event)

    async def send_body(self, send: ASGISendCallable, receive: ASGIReceiveCallable) -> None:
        """ Emit the response body. """
        event: HTTPResponseBodyEvent = {
            "type": "http.response.body",
            "body": self.body,
            "more_body": False,
        }
        await send(event)

    def _set_content_length(self, content_length: int) -> None:
        if self._should_set_content_length:
            self.headers.setdefault("content-length", str(content_length))

    def _check_body(self, body: bytes) -> None:
        if body and body != b"null":
            raise ImproperlyConfiguredException(
                "response content is not supported for HEAD responses and responses with a status code "
                "that does not allow content (304, 204, < 200)"
            )

    def _set_content_type(self, encoding: str, media_type: str) -> None:
        self.headers.setdefault(
            "content-type",
            (
                f"{media_type}; charset={encoding}"
                if media_type.startswith("text/") else media_type
            ),
        )

    def _set_headers(self, headers: dict[str, Any] | Iterable[tuple[str, str]] | None) -> None:
        if headers is not None:
            for key, value in headers.items() if isinstance(headers, dict) else headers:
                self.headers.append(key, value)

    def _get_content_length(self, body: bytes | str, content_length: int | None = None) -> int:
        if content_length is None:
            content_length = len(body)
        return content_length

    def _get_encoded_cookies(self, cookies: Iterable[Cookie] | None) -> tuple[tuple[bytes, bytes], ...]:
        return tuple(
            cookie.to_encoded_header() for cookie in (cookies or ()) if not cookie.documentation_only
        )


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
