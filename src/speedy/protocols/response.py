import datetime as dt
from abc import ABC, abstractmethod
from typing import Any, Literal, overload

from speedy.constants import SAMESITE
from speedy.datastructures import Cookie
from speedy.protocols.background import AbstractBackground
from speedy.status_code import HTTP_200_OK
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable


class AbstractResponse(ABC):
    """ A low-level ASGI response class. """

    def __init__(
            self,
            content: Any = None,
            status_code: int = HTTP_200_OK,
            headers: dict[str, str] | None = None,
            media_type: str | None = None,
            background: None | AbstractBackground = None
    ) -> None:
        self.status_code = status_code
        self.media_type = media_type
        self.background = background

    @abstractmethod
    def render(self, content: Any) -> bytes:
        ...

    @overload
    def set_cookie(self, /, key: Cookie) -> None:
        ...

    @overload
    def set_cookie(
            self,
            key: str,
            value: str = '',
            max_age: int | None = None,
            expires: dt.datetime | str | int | None = None,
            path: str = '/',
            domain: str | None = None,
            secure: bool = False,
            httponly: bool = False,
            samesite: Literal['lax', 'strict', 'none'] = 'lax'
    ) -> None:
        ...

    def set_cookie(
            self,
            key: str | Cookie,
            value: str = '',
            max_age: int | None = None,
            expires: dt.datetime | str | int | None = None,
            path: str = '/',
            domain: str | None = None,
            secure: bool = False,
            httponly: bool = False,
            samesite: Literal['lax', 'strict', 'none'] = 'lax'
    ) -> None:
        """ Set a cookie an the response. """
        assert samesite in SAMESITE, (
            'samesite must be either "lax", "strict" or "none"'
        )

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
            path: str = '/',
            domain: str | None = None
    ) -> None:
        """ Delete a cookie. """
        cookie = Cookie(
            key=key,
            path=path,
            domain=domain,
            expires=0,
            max_age=0
        )
        self.cookies = [var for var in self.cookies if var != cookie]
        self.cookies.append(cookie)

    async def __call__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable,
            send: ASGISendCallable
    ) -> None:
        raise NotImplemented
