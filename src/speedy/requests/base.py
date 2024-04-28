from collections.abc import Mapping
from typing import Any, Never

from speedy.enums import ScopeType
from speedy.types import Scope, ASGIReceiveCallable


async def empty_receive() -> Never:
    raise RuntimeError('Receive channel has not been made available')


async def empty_send() -> Never:
    raise RuntimeError('Send channel has not been made available')


class HTTPConnection(Mapping[str, Any]):
    def __init__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable | None = None
    ) -> None:
        assert scope['type'] in (ScopeType.HTTP, ScopeType.WEBSOCKET)

        self.scope = scope

    def __getitem__(self, item):
        return self.scope[item]

    def __iter__(self):
        return iter(self.scope)

    def __len__(self):
        return len(self.scope)
