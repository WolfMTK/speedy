from abc import ABC, abstractmethod
from typing import Iterator, Any

from speedy.protocols.request import AbstractRequest
from speedy.protocols.response import AbstractResponse
from speedy.protocols.websocket import AbstractWebSocket
from speedy.types import Message


class BaseEndpoint(ABC):
    """ Abstract class of the base endpoint. """

    def __await__(self) -> Iterator[Any]:
        return self.dispatch().__await__()

    @abstractmethod
    async def dispatch(self) -> None: ...


class BaseHTTPEndpoint(BaseEndpoint):
    """ Abstract class of the base http endpoints. """

    @abstractmethod
    async def method_not_allowed(self, request: AbstractRequest) -> AbstractResponse: ...


class BaseWebSocketEndpoint(BaseEndpoint):
    """ Abstract class of the base websocket endpoints. """

    @abstractmethod
    async def decode(self, websocket: AbstractWebSocket, message: Message) -> Any: ...

    @abstractmethod
    async def on_connect(self, websocket: AbstractWebSocket) -> None: ...

    @abstractmethod
    async def on_receive(self, websocket: AbstractWebSocket, data: Any) -> None: ...

    @abstractmethod
    async def on_disconnect(self, websocket: AbstractWebSocket, code: int) -> None: ...
