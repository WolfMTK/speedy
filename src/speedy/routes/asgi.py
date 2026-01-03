from typing import Any

from speedy.connection.base import ASGIConnection
from speedy.handlers import ASGIRouteHandler
from speedy.routes.base import BaseRoute
from speedy.types import Scope, Receive, Send


class ASGIRoute(BaseRoute[Scope]):
    """ An ASGI route. """

    def __init__(
            self,
            *,
            path: str,
            route_handler: ASGIRouteHandler,
    ) -> None:
        self.route_handler = route_handler
        super().__init__(path=path)

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ ASGI app that authorizes the connection and then awaits the handler function. """
        handler_scope = scope.copy()

        connection = ASGIConnection["ASGIRouteHandler", Any, Any, Any](
            scope=handler_scope,
            receive=receive,
            send=send,
        )
        await self.route_handler.handle(connection=connection)
