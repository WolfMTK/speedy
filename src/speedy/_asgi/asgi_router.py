from __future__ import annotations

from functools import lru_cache
from traceback import format_exc
from typing import TYPE_CHECKING, Any

from speedy._asgi.base import RegExpRouter, SmartRouter, TrieRouter
from speedy.exceptions import NotFoundException
from speedy.routes import HTTPRoute, WebSocketRoute, ASGIRoute
from speedy.types import (
    LifeSpanReceive,
    LifeSpanSend,
    LifespanShutdownCompleteEvent,
    LifespanStartupCompleteEvent,
    LifespanStartupFailedEvent,
    LifespanShutdownFailedEvent,
    Scope,
    Receive,
    Send,
    ExceptionHandlersMap,
    Method,
    ASGIAppType,
    RouteHandlerType,
    PathParameterDefinition,
)
from speedy.utils import normalize_path
from speedy.utils.scope import ScopeState

if TYPE_CHECKING:
    from speedy import Speedy


class ASGIRouter:
    """ Speedy ASGI router. """

    def __init__(self, app: Speedy) -> None:
        self._app_exception_handlers: ExceptionHandlersMap = app.exception_handlers
        self._router_initialized = False
        self.app = app
        self.router = SmartRouter(routers=[RegExpRouter(), TrieRouter()])

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope.setdefault("path_params", {})

        path = scope["path"]
        if root_path := scope.get("root_path", ""):
            path = path.split(root_path, maxsplit=1)[-1]
        normalized_path = normalize_path(path)

        try:
            asgi_app, route_handler, scope["path"], scope["path_params"], path_template = self.handle_routing(
                path=normalized_path,
                method=scope.get("method"),
            )
        except Exception:
            ScopeState.from_scope(scope).exception_handlers = self._app_exception_handlers
            raise
        else:
            ScopeState.from_scope(scope).exception_handlers = route_handler.exception_handlers
            scope["route_handler"] = route_handler
            scope["path_template"] = path_template

        await asgi_app(scope, receive, send)

    @lru_cache(1024)
    def handle_routing(
            self,
            path: str,
            method: Method | None,
    ) -> tuple[ASGIAppType, RouteHandlerType, str, dict[str, Any], str]:
        result = self.router.match(path=path, method=method)
        if result is not None:
            asgi_app, handler, path_params, path_template = result
            return asgi_app, handler, path, path_params, path_template
        raise NotFoundException()

    async def lifespan(self, receive: LifeSpanReceive, send: LifeSpanSend) -> None:
        """ Handle the ASGI `lifespan` event on application startup and shutdown. """
        startup_event: LifespanStartupCompleteEvent = {"type": "lifespan.startup.complete"}
        shutdown_event: LifespanShutdownCompleteEvent = {"type": "lifespan.shutdown.complete"}

        await receive()
        started = False
        try:
            async with self.app.lifespan():
                await send(startup_event)
                started = True
                await receive()
        except BaseException as e:
            formatted_exception = format_exc()

            if started:
                fail_message: LifespanShutdownFailedEvent = {
                    "type": "lifespan.shutdown.failed",
                    "message": formatted_exception,
                }
            else:
                fail_message: LifespanStartupFailedEvent = {
                    "type": "lifespan.startup.failed",
                    "message": formatted_exception,
                }

            await send(fail_message)
            raise e

        await send(shutdown_event)

    def construct_routing_trie(self) -> None:
        """ Create a map of the app's routes. """
        if self._router_initialized:
            self.router.clear()

        for route in self.app.routes:
            self._add_route(route)

        self.router.construct()
        self._router_initialized = True

    def _add_route(self, route: HTTPRoute | WebSocketRoute | ASGIRoute) -> None:
        param_names = [
            param.name for param in route.path_components
            if isinstance(param, PathParameterDefinition)
        ]
        is_dynamic = len(param_names) > 0
        if isinstance(route, HTTPRoute):
            for route_handler in route.route_handlers:
                for method in route_handler.http_methods:
                    self.router.add_route(
                        path=route.path,
                        method=method,
                        path_components=route.path_components,
                        asgi_app=route.handle,
                        handler=route_handler,
                        is_dynamic=is_dynamic,
                    )
        elif isinstance(route, WebSocketRoute) or isinstance(route, ASGIRoute):
            _method = {
                WebSocketRoute: "websocket",
                ASGIRoute: "asgi"
            }
            self.router.add_route(
                path=route.path,
                method=_method.get(type(route)),
                path_components=route.path_components,
                asgi_app=route.handle,
                handler=route.route_handler,
                is_dynamic=is_dynamic,
            )
