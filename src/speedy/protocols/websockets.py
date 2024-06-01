from abc import ABC

from speedy.types import ASGIReceiveCallable


class AbstractWebsocket(ABC):
    def receive_wrapper(self, receive: ASGIReceiveCallable) -> ASGIReceiveCallable: ...
