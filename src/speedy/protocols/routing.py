from abc import ABC

from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable


class BaseRoute(ABC):
    """ Base route class. """

    async def handle(
            self, scope: Scope,
            receive: ASGIReceiveCallable,
            send: ASGISendCallable
    ) -> None:
        """ ASGI App of the route. """
