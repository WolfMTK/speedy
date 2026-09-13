from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from speedy.datastructures import State, URLPath
from speedy.middleware import Middleware, _AbstractMiddleware
from speedy.middleware.body_limit import RequestBodyLimitMiddleware
from speedy.middleware.error import ServerErrorMiddleware
from speedy.middleware.exceptions import ExceptionMiddleware
from speedy.requests import Request
from speedy.responses import Response
from speedy.routing import BaseRoute, Router
from speedy.status import HTTP_500_INTERNAL_SERVER_ERROR
from speedy.types import ASGIApplication, ExceptionHandler, Lifespan, Receive, Scope, Send


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
        self.exception_handlers = {} if exception_handler is None else dict(exception_handler)
        self.user_middleware = [] if middleware is None else list(middleware)
        self.middleware_stack: ASGIApplication | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = self
        if self.middleware_stack is None:
            self.middleware_stack = self.build_middleware_stack()
        await self.middleware_stack(scope, receive, send)

    @property
    def routes(self) -> list[BaseRoute]:
        return self.router.routes

    def build_middleware_stack(self) -> ASGIApplication:
        debug = self.debug
        error_handler = None
        exception_handlers: dict[Any, ExceptionHandler] = {}

        for key, value in self.exception_handlers.items():
            if key in (HTTP_500_INTERNAL_SERVER_ERROR, Exception):
                error_handler = value
            else:
                exception_handlers[key] = value

        middleware = [Middleware(ServerErrorMiddleware, handler=error_handler, debug=debug)]
        if self.max_body_size is not None:
            middleware.append(Middleware(RequestBodyLimitMiddleware, max_body_size=self.max_body_size))
        middleware += self.user_middleware
        middleware.append(Middleware(ExceptionMiddleware, handlers=exception_handlers, debug=debug))

        app = self.router
        for cls, args, kwargs in reversed(middleware):
            app = cls(app, *args, **kwargs)
        return app

    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath:
        return self.router.url_path_for(name, **path_params)

    def mount(self, path: str, app: ASGIApplication, name: str | None = None) -> None:
        self.router.mount(path, app=app, name=name)

    def host(self, host: str, app: ASGIApplication, name: str | None = None) -> None:
        self.router.host(host, app=app, name=name)

    def add_middleware[**P](self, middleware_class: _AbstractMiddleware[P], *args: P.args, **kwargs: P.kwargs) -> None:
        if self.middleware_stack is not None:
            raise RuntimeError("Cannot add middleware after an application has started")
        self.user_middleware.insert(0, Middleware(middleware_class, *args, **kwargs))

    def add_exception_handler(
        self,
        exc_class_or_status_code: int | type[Exception],
        handler: ExceptionHandler,
    ) -> None:
        self.exception_handlers[exc_class_or_status_code] = handler

    def add_route(
        self,
        path: str,
        route: Callable[[Request], Awaitable[Response] | Response],
        methods: list[str] | None = None,
        name: str | None = None,
        include_in_schema: bool = True,
    ) -> None:
        self.router.add_route(path, route, methods=methods, name=name, include_in_schema=include_in_schema)

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
