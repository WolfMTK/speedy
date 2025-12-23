from __future__ import annotations

from typing import Sequence, Mapping

from speedy.datastructures import Cookie, ResponseHeader
from speedy.types import ResponseCookies, ResponseHeaders


def narrow_response_cookies(cookies: ResponseCookies | None) -> Sequence[Cookie]:
    """ Convert response cookies into a normalized sequence of Cookie objects. """
    if cookies is None:
        return ()
    if isinstance(cookies, Mapping):
        return tuple(Cookie(key=key, value=value) for key, value in cookies.items())
    return tuple(cookies)


def narrow_response_headers(headers: ResponseHeaders | None) -> Sequence[ResponseHeader]:
    """ Convert response headers into a normalized sequence of ResponseHeader objects. """
    if headers is None:
        return ()
    if isinstance(headers, Mapping):
        return tuple(ResponseHeader(name=name, value=value) for name, value in headers.items())
    return tuple(headers)
