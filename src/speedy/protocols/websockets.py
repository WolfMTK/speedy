from abc import ABC, abstractmethod
from typing import Iterable

from speedy.datastructures import Headers
from speedy.types import ASGIReceiveCallable, ASGISendCallable


class AbstractWebsocket(ABC):
    @abstractmethod
    def receive_wrapper(self, receive: ASGIReceiveCallable) -> ASGIReceiveCallable: ...

    @abstractmethod
    def send_wrapper(self, send: ASGISendCallable) -> ASGIReceiveCallable: ...

    @abstractmethod
    def close(self, code: int, reason: str | None) -> None: ...

    @abstractmethod
    def accept(
            self,
            subprotocols: str | None = None,
            headers: Headers | Iterable[tuple[bytes, bytes]] | None = None
    ): ...
