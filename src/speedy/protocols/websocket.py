from abc import abstractmethod
from collections.abc import AsyncIterator
from typing import Protocol, Any, Literal

from speedy.datastructures import Headers
from speedy.protocols.connection import Connection, StateT, AuthT, UserT
from speedy.types import ASGIReceiveCallable, ASGISendCallable

WebSocketMode = Literal['text', 'bytes']


class AbstractWebSocket(Protocol[UserT, AuthT, StateT], Connection[UserT, AuthT, StateT]):
    @abstractmethod
    def receive_wrapper(self, receive: ASGIReceiveCallable) -> ASGIReceiveCallable: ...

    @abstractmethod
    def send_wrapper(self, send: ASGISendCallable) -> ASGISendCallable: ...

    @abstractmethod
    async def accept(
            self,
            subprotocol: str | None = None,
            headers: Headers | dict[str, Any] | list[tuple[bytes, bytes]] | None = None
    ) -> None: ...

    @abstractmethod
    async def receive_data(self, mode: WebSocketMode) -> str | bytes: ...

    @abstractmethod
    async def receive_text(self) -> str: ...

    @abstractmethod
    async def receive_bytes(self) -> bytes: ...

    @abstractmethod
    async def receive_json(self, mode: WebSocketMode = 'text') -> Any: ...

    @abstractmethod
    async def iter_text(self) -> AsyncIterator[str]: ...

    @abstractmethod
    async def iter_bytes(self) -> AsyncIterator[bytes]: ...

    @abstractmethod
    async def iter_json(self, mode: WebSocketMode = 'text') -> AsyncIterator[Any]: ...

    @abstractmethod
    async def send_data(self, data: str | bytes, mode: WebSocketMode = 'text', encoding: str = 'utf-8') -> None: ...

    @abstractmethod
    async def send_text(self, data: bytes, encoding: str = 'utf-8') -> None: ...

    @abstractmethod
    async def send_bytes(self, data: bytes, encoding: str = 'utf-8') -> None: ...

    @abstractmethod
    async def send_json(self, data: Any, mode: WebSocketMode = 'text', encoding: str = 'utf-8') -> None: ...
