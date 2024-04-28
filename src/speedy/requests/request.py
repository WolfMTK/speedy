from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable
from .base import HTTPConnection, empty_receive, empty_send


class Request(HTTPConnection):
    def __init__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable = empty_receive,
            send: ASGISendCallable = empty_send
    ) -> None:
        super().__init__(scope, receive)
        self._scope = scope
        self._receive = receive
        self._send = send

    @property
    def method(self) -> str:
        return self._scope['method']

    @property
    def receive(self) -> ASGIReceiveCallable:
        return self._receive
