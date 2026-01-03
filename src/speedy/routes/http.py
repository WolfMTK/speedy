from speedy.routes.base import BaseRoute
from speedy.types import HTTPScope, Receive, Send


class HTTPRoute(BaseRoute[HTTPScope]):
    """ An HTTP route. """

    def __init__(
            self,
            *,
            path: str,
    ) -> None:
        super().__init__(path=path)

    async def handle(self, scope: HTTPScope, receive: Receive, send: Send) -> None:
        """ ASGI app of the route. """
