from collections.abc import Mapping, Sequence
from typing import Any

from speedy.datastructures import State
from speedy.routing import BaseRoute, Router
from speedy.types import ASGIApplication, ExceptionHandler, Lifespan, Middleware, Receive, Scope, Send


class Speedy:
    def __init__(
        self,
        debug: bool = False,
        routes: Sequence[BaseRoute] | None = None,
        middleware: Sequence[Middleware] | None = None,
        exception_handler: Mapping[Any, ExceptionHandler] | None = None,
        lifespan: Lifespan | None = None,
        *,
        max_body_size: int | None = None,
    ) -> None:
        self.debug = debug
        self.state = State()
        self.router = Router(routes, lifespan=lifespan)
        self.max_body_size = max_body_size
        self.exception_handler = {} if exception_handler is None else dict(exception_handler)
        self.user_middleware = [] if middleware is None else list(middleware)
        self.middleware_stack: ASGIApplication | None = None

    def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = self

    def get(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def put(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def post(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def delete(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def options(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def head(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def path(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def trace(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def websocket(self) -> None:
        # TODO: add decoration WebSocket
        ...

    def exception_handler(self) -> None:
        # TODO: add decoration ExceptionHandler
        ...

    def middleware(self) -> None:
        # TODO: add decoration Middleware
        ...
