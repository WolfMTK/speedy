from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from speedy.status_code import WS_1000_NORMAL_CLOSURE
from speedy.types import Message


class AbstractWebSocket(ABC):
    @property
    @abstractmethod
    def client_state(self) -> str: ...

    @property
    @abstractmethod
    def application_state(self) -> str: ...

    @abstractmethod
    async def send(self, message: Message) -> None: ...

    @abstractmethod
    async def send_text(self, data: str) -> None: ...

    @abstractmethod
    async def send_bytes(self, data: bytes) -> None: ...

    @abstractmethod
    async def send_json(self, data: Any, mode: str, *, json_library: str) -> None: ...

    @abstractmethod
    async def receive(self) -> Message: ...

    @abstractmethod
    async def receive_text(self) -> str: ...

    @abstractmethod
    async def receive_bytes(self) -> bytes: ...

    @abstractmethod
    async def receive_json(self, mode: str, *, json_library: str) -> Any: ...

    @abstractmethod
    async def accept(
            self,
            subprotocol: str | None = None,
            headers: Iterable[tuple[bytes, bytes]] | None = None
    ) -> None: ...

    @abstractmethod
    async def close(
            self,
            code: int = WS_1000_NORMAL_CLOSURE,
            reason: str | None = None
    ) -> None: ...
