from abc import ABC

from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable


class BaseASGIApplication(ABC):
    """ Base ASGI application protocol. """

    async def __call__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable,
            send: ASGISendCallable
    ) -> None: ...
