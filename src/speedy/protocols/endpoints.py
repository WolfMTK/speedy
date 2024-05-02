from abc import ABC, abstractmethod
from typing import Iterator, Any

from speedy.request import Request
from speedy.types import Message
from speedy.websocket import WebSocket


class BaseEndpoint(ABC):
    """ Abstract class of the base endpoint. """

    def __await__(self) -> Iterator[Any]:
        return self.dispatch().__await__()

    @abstractmethod
    async def dispatch(self) -> None: ...


class BaseHTTPEndpoint(BaseEndpoint):
    """ Abstract class of the base http endpoints. """

    @abstractmethod
    async def method_not_allowed(self, request: Request): ...


class BaseWebSocketEndpoint(BaseEndpoint):
    """ Abstract class of the base websocket endpoints. """

    @abstractmethod
    async def decode(self, websocket: WebSocket, message: Message) -> Any: ...

    @abstractmethod
    async def on_connect(self, websocket: WebSocket) -> None: ...

    @abstractmethod
    async def on_receive(self, websocket: WebSocket, data: Any) -> None: ...

    @abstractmethod
    async def on_disconnect(self, websocket: WebSocket, code: int) -> None: ...
