from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Mapping

from speedy.datastructures import MutableHeaders
from speedy.datastructures.cookie import Cookie
from speedy.types import ASGISendCallable, ASGIReceiveCallable, Scope
from speedy.types.application import SAMESITE


class AbstractResponse(ABC):
    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        raise NotImplementedError("The object's signature does not match the abstract class")

    @property
    @abstractmethod
    def raw_header(self) -> list[tuple[bytes, bytes]]: ...

    @property
    @abstractmethod
    def headers(self) -> MutableHeaders: ...

    @abstractmethod
    def set_cookie(
            self,
            key: str | Cookie,
            value: str,
            max_age: int | None,
            expires: datetime | str | int | None,
            path: str | None,
            domain: str | None,
            secure: bool,
            httponly: bool,
            samesite: SAMESITE
    ) -> None: ...

    @abstractmethod
    def delete_cookie(
            self,
            key: str,
            path: str,
            domain: str | None,
            secure: bool,
            httponly: bool,
            samesite: SAMESITE
    ) -> None: ...

    @abstractmethod
    async def start_response(self, prefix: str, send: ASGISendCallable) -> None: ...

    @abstractmethod
    async def send_body(self, prefix: str, send: ASGISendCallable, receive: ASGIReceiveCallable) -> None: ...

    @abstractmethod
    def render(self, content: Any | None) -> bytes: ...

    @abstractmethod
    def init_headers(self, headers: Mapping[str, str] | None = None) -> None: ...
