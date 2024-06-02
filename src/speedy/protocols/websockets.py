from abc import ABC
from typing import TypeVar, Iterable

from speedy.datastructures import Headers
from speedy.types import ASGIReceiveCallable, ASGISendCallable


class AbstractWebsocket(ABC):
    def receive_wrapper(self, receive: ASGIReceiveCallable) -> ASGIReceiveCallable: ...

    def send_wrapper(self, send: ASGISendCallable) -> ASGIReceiveCallable: ...

    def close(self, code: int, reason: str | None) -> None: ...

    def accept(
            self,
            subprotocols: str | None = None,
            headers: Headers | Iterable[tuple[bytes, bytes]] | None = None
    ): ...
