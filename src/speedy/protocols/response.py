from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Mapping

from speedy import BackgroundTask, MediaType
from speedy.datastructures import MutableHeaders
from speedy.datastructures.cookie import Cookie
from speedy.types import ASGISendCallable, ASGIReceiveCallable, Scope
from speedy.types.application import SAMESITE


class AbstractASGIResponse(ABC):
    @abstractmethod
    def __init__(
            self,
            content: Any | None,
            status_code: int,
            encoding: str,
            cookie: Sequence[Cookie] | Mapping[str, str] | None,
            headers: Mapping[str, str] | None,
            media_type: MediaType | str | None,
            background: BackgroundTask | None
    ) -> None: ...

    @abstractmethod
    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None: ...


class AbstractBaseResponse(ABC):
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


class AbstractResponse(AbstractBaseResponse, AbstractASGIResponse, ABC):
    pass


class AbstractMediaTypeResponse(AbstractASGIResponse, AbstractBaseResponse, ABC):
    @abstractmethod
    def __init__(
            self,
            content: Any | None,
            status_code: int,
            encoding: str,
            cookie: Sequence[Cookie] | Mapping[str, str] | None,
            headers: Mapping[str, str] | None,
            background: BackgroundTask | None
    ) -> None: ...


class AbstractJSONResponse(AbstractASGIResponse, AbstractBaseResponse, ABC):
    @abstractmethod
    def __init__(
            self,
            content: Any | None,
            status_code: int,
            library_json: str,
            encoding: str,
            cookie: Sequence[Cookie] | Mapping[str, str] | None,
            headers: Mapping[str, str] | None,
            background: BackgroundTask | None
    ) -> None: ...

    @property
    @abstractmethod
    def library(self) -> str: ...
