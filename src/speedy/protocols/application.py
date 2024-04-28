from typing import Protocol

from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable


class BaseASGIApplication(Protocol):
    """ Base ASGI application protocol. """

    async def __call__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable,
            send: ASGISendCallable
    ) -> None: ...
