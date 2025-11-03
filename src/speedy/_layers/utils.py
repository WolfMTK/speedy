from __future__ import annotations

from typing import Sequence, Mapping

from speedy.datastructures import Cookie
from speedy.types import ResponseCookies


def narrow_response_cookies(cookies: ResponseCookies | None) -> Sequence[Cookie]:
    """ Convert response cookies into a normalized sequence of Cookie objects. """
    if cookies is None:
        return ()
    if isinstance(cookies, Mapping):
        return tuple(Cookie(key=key, value=value) for key, value in cookies.items())
    return tuple(cookies)
