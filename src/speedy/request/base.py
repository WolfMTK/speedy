from typing import Never

from speedy.enums import ScopeType
from speedy.protocols import HTTPConnection
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable


async def empty_receive() -> Never:
    raise RuntimeError('Receive channel has not been made available')


async def empty_send() -> Never:
    raise RuntimeError('Send channel has not been made available')


class Request(HTTPConnection):
    def __init__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable = empty_receive,
            send: ASGISendCallable = empty_send
    ) -> None:
        assert scope['type'] == ScopeType.HTTP

        self._scope = scope
        self._receive = receive
        self._send = send

    @property
    def method(self) -> str:
        return self._scope['method']

    @property
    def receive(self) -> ASGIReceiveCallable:
        return self._receive
