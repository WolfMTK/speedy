import itertools
from typing import Iterable

from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.handlers.http_handlers.base import HTTPRouteHandler
from speedy.routes.base import BaseRoute
from speedy.types import HTTPScope, Receive, Send, HttpMethodName


class HTTPRoute(BaseRoute[HTTPScope]):
    """ An HTTP route. """

    def __init__(
            self,
            *,
            path: str,
            route_handlers: Iterable[HTTPRouteHandler],
    ) -> None:
        super().__init__(path=path)
        self.route_handler_map = self.create_handler_map(route_handlers)
        try:
            self.methods, self.route_handlers = zip(*self.route_handler_map.items())
        except ValueError:
            self.methods, self.route_handlers = (), ()

    async def handle(self, scope: HTTPScope, receive: Receive, send: Send) -> None:
        """ ASGI app that creates a Request from the passed in args, determines which handler function
        to call and then handles the call. """
        route_handler = self.route_handler_map[scope["method"]]
        connection = route_handler.request_class(scope=scope, receive=receive, send=send)
        await route_handler.handle(connection=connection)

    def create_handler_map(
            self,
            route_handlers: Iterable[HTTPRouteHandler],
    ) -> dict[HttpMethodName, HTTPRouteHandler]:
        """ Create a mapping of HTTP method names to route handlers. """
        method_handler_pairs = itertools.chain.from_iterable(
            ((http_method, handler) for http_method in handler.http_methods)
            for handler in route_handlers,
        )
        handler_map = {}
        for http_method, handler in method_handler_pairs:
            if http_method in handler_map:
                raise ImproperlyConfiguredException(
                    f"Handler already registered for path {self.path!r} and http method {http_method}",
                )
            handler_map[http_method] = handler
        return handler_map
