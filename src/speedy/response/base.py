from __future__ import annotations

import itertools
import re
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import TypeVar, Any, ClassVar, Generic, overload

from speedy import BackgroundTask, BackgroundTasks, MediaType
from speedy.connection.request import Request
from speedy.datastructures import MutableHeaders, Cookie, ETag
from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.serialization import encode_json, encode_msgpack
from speedy.serialization.base import default_serializer
from speedy.status_code import HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_304_NOT_MODIFIED
from speedy.types import (
    Scope,
    Receive,
    Send,
    SAMESITE,
    ResponseHeaders,
    Empty,
    Serializer,
)
from speedy.types.asgi_types import HTTPResponseStartEvent, HTTPResponseBodyEvent
from speedy.types.composite_types import ResponseCookies, TypeEncodersMap
from speedy.utils.helpers import get_enum_string_value

T = TypeVar('T')

MEDIA_TYPE_APPLICATION_JSON_PATTERN = re.compile(r"^application/(?:.+\+)?json")


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

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
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

    async def start_response(self, send: Send) -> None:
        """ Emit the start event of the response. This event includes the headers and status codes. """
        event: HTTPResponseStartEvent = {
            "type": "http.response.start",
            "status": self.status_code,
            "headers": self.encode_headers(),
        }
        await send(event)

    async def send_body(self, send: Send, receive: Receive) -> None:
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
    """ Base Litestar HTTP response class, used as the basis for all other response classes. """

    content: T
    type_encoders: TypeEncodersMap | None = None

    def __init__(
            self,
            content: T | None = None,
            background: BackgroundTask | BackgroundTasks | None = None,
            cookies: ResponseCookies | None = None,
            encoding: str = 'utf-8',
            headers: ResponseHeaders | None = None,
            media_type: MediaType | str | None = None,
            status_code: int | None = HTTP_200_OK,
            type_encoders: TypeEncodersMap | None = None,
    ) -> None:
        self.content = content
        self.background = background
        self.cookies: list[Cookie] = (
            [Cookie(key=key, value=value) for key, value in cookies.items()]
            if isinstance(cookies, Mapping)
            else list(cookies or [])
        )
        self.encoding = encoding
        self.headers: dict[str, Any] = (
            dict(headers) if isinstance(headers, Mapping) else {h.name: h.value for h in headers or {}}
        )
        self.status_code = status_code
        self.media_type = media_type
        self.response_type_encoders = {**(self.type_encoders or {}), **(type_encoders or {})}

    @overload
    def set_cookie(self, /, cookie: Cookie) -> None:
        ...

    @overload
    def set_cookie(
            self,
            key: str,
            value: str | None = None,
            max_age: int | None = None,
            expires: int | None = None,
            path: str = "/",
            domain: str | None = None,
            secure: bool = False,
            httponly: bool = False,
            samesite: SAMESITE = "lax",
    ) -> None:
        ...

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
            max_age=0,
            expires=0,
            path=path,
        )
        self.cookies = [val for val in self.cookies if val != cookie]
        self.cookies.append(cookie)

    def set_header(self, key: str, value: Any) -> None:
        """ Set a header on the response. """
        self.headers[key] = value

    def set_etag(self, etag: str | ETag) -> None:
        """ Set an etag header. """
        self.headers["etag"] = etag.to_header() if isinstance(etag, ETag) else etag

    def render(self, content: Any, media_type: str, enc_hook: Serializer = default_serializer) -> bytes:
        """ Handle the rendering of content into a bytes string. """
        if isinstance(content, bytes):
            return content

        if content is Empty:
            raise RuntimeError("The `Empty` sentinel cannot be used as response content")

        try:
            if media_type.startswith("text/") and not content:
                return b""

            if isinstance(content, str):
                return content.encode(self.encoding)

            if media_type == MediaType.MESSAGEPACK:
                return encode_msgpack(content, enc_hook)

            if MEDIA_TYPE_APPLICATION_JSON_PATTERN.match(
                    media_type,
            ):
                return encode_json(content, enc_hook)

            raise ImproperlyConfiguredException(f"unsupported media_type {media_type} for content {content!r}")
        except (AttributeError, ValueError, TypeError) as e:
            raise ImproperlyConfiguredException("Unable to serialize response content") from e

    def to_asgi_response(
            self,
            request: Request,
            *,
            background: BackgroundTask | BackgroundTasks | None = None,
            cookies: Iterable[Cookie] | None = None,
            headers: dict[str, str] | None = None,
            is_head_response: bool = False,
            media_type: MediaType | str | None = None,
            status_code: int | None = None,
    ) -> ASGIResponse:
        """ Create an ASGIResponse from a Response instance. """
        headers = {**headers, **self.headers} if headers is not None else self.headers
        cookies = self.cookies if cookies is None else itertools.chain(self.cookies, cookies)
        media_type = get_enum_string_value(self.media_type or media_type or MediaType.JSON)
        return ASGIResponse(
            background=self.background or background,
            body=self.render(self.content, media_type),
            cookies=cookies,
            encoding=self.encoding,
            headers=headers,
            is_head_response=is_head_response,
            media_type=self.media_type or media_type,
            status_code=self.status_code or status_code,
        )
