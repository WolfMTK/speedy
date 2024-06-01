from typing import Any, Never

from speedy.datastructures import URL
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable, Message
from speedy.types.application import ASGIAppType


def empty_receive() -> Never:
    raise RuntimeError()


def empty_send(_: Message) -> Never:
    raise RuntimeError


class ASGIConnect:
    def __init__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        self.scope = scope
        self.receive = receive
        self.send = send

    @property
    def app(self) -> ASGIAppType:
        return self.scope['app']

    @property
    def url(self) -> URL:
        if not hasattr(self, '_url'):
            self._url = URL.from_scope(self.scope)
        return self._url

    @property
    def path_params(self) -> dict[str, Any]:
        return self.scope.get('path_params', {})
