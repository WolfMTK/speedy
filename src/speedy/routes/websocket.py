from speedy.routes.base import BaseRoute
from speedy.types import WebSocketScope, Receive, Send


class WebSocketRoute(BaseRoute[WebSocketScope]):
    """ A websocket route. """

    def __init__(
            self,
            *,
            path: str,
    ) -> None:
        super().__init__(path=path)

    async def handle(self, scope: WebSocketScope, receive: Receive, send: Send) -> None:
        """ ASGI app of the route. """
