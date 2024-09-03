from abc import abstractmethod
from typing import AsyncGenerator, Protocol, Any

from speedy.datastructures import FormMultiDict
from speedy.protocols.connection import Connection, UserT, AuthT, StateT
from speedy.types import Method


class AbstractRequest(Protocol[UserT, AuthT, StateT], Connection[UserT, AuthT, StateT]):
    @property
    @abstractmethod
    def method(self) -> Method: ...

    @property
    @abstractmethod
    def content_type(self) -> tuple[str, dict[str, str]]: ...

    @abstractmethod
    async def stream(self) -> AsyncGenerator[bytes, None]: ...

    @abstractmethod
    async def body(self) -> bytes: ...

    @abstractmethod
    async def json(self) -> Any: ...

    @abstractmethod
    async def form(self, multipart_limit: int = 1000) -> FormMultiDict: ...

    @abstractmethod
    async def send_push_promise(self, path: str) -> None: ...
