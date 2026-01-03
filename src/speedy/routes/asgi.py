from speedy.routes.base import BaseRoute
from speedy.types import Scope, Receive, Send


class ASGIRoute(BaseRoute[Scope]):
    """ An ASGI route. """

    def __init__(
            self,
            *,
            path: str,
    ) -> None:
        super().__init__(path=path)

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ ASGI app of the route. """
