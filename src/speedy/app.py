from __future__ import annotations

import collections
import functools
import inspect
import logging
import os
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncGenerator, Iterable, Mapping, Sequence, cast

from speedy import Router
from speedy._asgi import ASGIRouter, wrap_in_exception_handler
from speedy.config import ApplicationConfig, BaseLoggingConfig, LoggingConfig
from speedy.config.allowed_hosts import AllowedHostsConfig
from speedy.config.cors import CORSConfig
from speedy.config.logging import get_logger_placeholder
from speedy.connection import Request, WebSocket
from speedy.constants import MULTIPART_FORM_PART_LIMIT, REQUEST_MAX_BODY_SIZE
from speedy.datastructures import ETag, State
from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.handlers import ASGIRouteHandler
from speedy.handlers.base import BaseRouteHandler
from speedy.handlers.http_handlers.base import HTTPRouteHandler
from speedy.handlers.websocket_handlers.base import WebsocketRouteHandler
from speedy.protocols import ILogger
from speedy.routes import ASGIRoute, HTTPRoute, WebSocketRoute
from speedy.types import (
    AfterExceptionHookHandler,
    AfterRequestHookHandler,
    AfterResponseHookHandler,
    ASGIAppType,
    BeforeMessageSendHookHandler,
    BeforeRequestHookHandler,
    ControllerRouterHandler,
    Empty,
    EmptyType,
    ExceptionHandlersMap,
    GetLogger,
    Lifespan,
    LifespanHook,
    LifeSpanReceive,
    LifespanScope,
    LifeSpanSend,
    Message,
    Middleware,
    ParametersMap,
    Receive,
    ResponseCookies,
    ResponseHeaders,
    RouteHanderMapItem,
    RouteHandlerType,
    Scope,
    Send,
    TypeDecodersSequence,
    TypeEncodersMap,
)
from speedy.utils.predicates import is_async_callable
from speedy.utils.sync import ensure_async_callable

if TYPE_CHECKING:
    from speedy.response import Response


class Speedy(Router):
    def __init__(
        self,
        route_handlers: Sequence[ControllerRouterHandler] | None = None,
        *,
        after_exception: Sequence[AfterExceptionHookHandler] | None = None,
        after_request: AfterRequestHookHandler | None = None,
        after_response: AfterResponseHookHandler | None = None,
        allowed_hosts: Sequence[str] | AllowedHostsConfig | None = None,
        before_request: BeforeRequestHookHandler | None = None,
        before_send: Sequence[BeforeMessageSendHookHandler] | None = None,
        cors_config: CORSConfig | None = None,
        debug: bool | None = None,
        etag: ETag | None = None,
        exception_handlers: ExceptionHandlersMap | None = None,
        logging_config: BaseLoggingConfig | EmptyType | None = Empty,
        middleware: Sequence[Middleware] | None = None,
        multipart_form_part_limit: int = MULTIPART_FORM_PART_LIMIT,
        on_shutdown: Sequence[LifespanHook] | None = None,
        on_startup: Sequence[LifespanHook] | None = None,
        opt: Mapping[str, Any] | None = None,
        parameters: ParametersMap | None = None,
        path: str | None = None,
        request_class: type[Request] | None = None,
        request_max_body_size: int | None = REQUEST_MAX_BODY_SIZE,
        response_class: type[Response] | None = None,
        response_cookies: ResponseCookies | None = None,
        response_headers: ResponseHeaders | None = None,
        signature_namespace: Mapping[str, Any] | None = None,
        signature_types: Sequence[Any] | None = None,
        state: State | None = None,
        tags: Sequence[str] | None = None,
        type_decoders: TypeDecodersSequence | None = None,
        type_encoders: TypeEncodersMap | None = None,
        websocket_class: type[WebSocket] | None = None,
        lifespan: Lifespan = None,
    ) -> None:
        if logging_config is Empty:
            logging_config = LoggingConfig()

        if debug is None:
            debug = os.getenv("SPEEDY_DEBUG", "0") == "1"

        if not isinstance(allowed_hosts, AllowedHostsConfig):
            allowed_hosts = list(allowed_hosts or [])

        config = ApplicationConfig(
            after_exception=list(after_exception or []),
            after_request=after_request,
            after_response=after_response,
            allowed_hosts=allowed_hosts,
            before_request=before_request,
            before_send=list(before_send or []),
            cors_config=cors_config,
            debug=debug,
            etag=etag,
            exception_handlers=exception_handlers or {},
            logging_config=logging_config,
            lifespan=list(lifespan or []),
            middleware=list(middleware or []),
            multipart_form_part_limit=multipart_form_part_limit,
            on_startup=list(on_startup or []),
            on_shutdown=list(on_shutdown or []),
            opt=dict(opt or {}),
            path=path or "",
            parameters=parameters or {},
            request_class=request_class,
            request_max_body_size=request_max_body_size,
            response_class=response_class,
            response_cookies=response_cookies or {},
            response_headers=response_headers or {},
            route_handlers=list(route_handlers) if route_handlers is not None else [],
            signature_namespace=dict(signature_namespace or {}),
            signature_types=list(signature_types or []),
            state=state or State(),
            tags=list(tags or []),
            type_decoders=type_decoders,
            type_encoders=type_encoders,
            websocket_class=websocket_class,
        )

        self._debug: bool = True
        self._lifespan_managers = config.lifespan

        self.get_logger: GetLogger = get_logger_placeholder
        self.logger: ILogger | None = None

        self.after_exception = [
            ensure_async_callable(header) for header in config.after_exception
        ]
        self.allowed_hosts = config.allowed_hosts
        self.before_send = [
            ensure_async_callable(header) for header in config.before_send
        ]
        self.cors_config = config.cors_config
        self.logging_config = config.logging_config
        self.multipart_form_part_limit = config.multipart_form_part_limit
        self.on_startup = config.on_startup
        self.on_shutdown = config.on_shutdown
        self.request_class: type[Request] = config.request_class or Request
        self.state = config.state
        self.websocket_class: type[WebSocket] = config.websocket_class or WebSocket
        self.debug = config.debug

        super().__init__(
            after_request=config.after_request,
            after_response=config.after_response,
            before_request=config.before_request,
            etag=config.etag,
            exception_handlers=config.exception_handlers,
            middleware=config.middleware,
            opt=config.opt,
            parameters=config.parameters,
            path=config.path,
            request_class=self.request_class,
            request_max_body_size=request_max_body_size,
            response_class=config.response_class,
            response_cookies=config.response_cookies,
            response_headers=config.response_headers,
            route_handlers=config.route_handlers,
            signature_namespace=config.signature_namespace,
            signature_types=config.signature_types,
            tags=config.tags,
            type_encoders=config.type_encoders,
            type_decoders=config.type_decoders,
            websocket_class=self.websocket_class,
        )

        self.asgi_router = ASGIRouter(app=self)

        self.routes = self._build_routes(
            self._reduce_handlers(self.route_handlers),
        )
        self.route_handler_method_map = _create_route_handler_method_map(self.routes)

        self.route_handlers = ()

        self.asgi_router.construct_routing_trie()

        if self.logging_config:
            self.get_logger = self.logging_config.configure()
            self.logger = self.get_logger("speedy")

        self.asgi_handler = self._create_asgi_handler()

    async def __call__(
        self,
        scope: Scope | LifespanScope,
        receive: Receive | LifeSpanReceive,
        send: Send | LifeSpanSend,
    ) -> None:
        if scope["type"] == "lifespan":
            await self.asgi_router.lifespan(
                receive=cast("LifeSpanReceive", receive),
                send=cast("LifeSpanSend", send),
            )
            return

        scope["app"] = self
        scope.setdefault("state", {})
        await self.asgi_handler(
            scope,
            receive,
            self._wrap_send(
                send=cast("Send", send),
                scope=cast("Scope", scope),
            ),
        )

    @property
    def debug(self) -> bool:
        return self._debug

    @debug.setter
    def debug(self, value: bool) -> None:
        if self.logger and self.logging_config:
            self.logging_config.set_level(
                self.logger, logging.DEBUG if value else logging.INFO
            )
        self._debug = value

    @asynccontextmanager
    async def lifespan(self) -> AsyncGenerator[None, None]:
        """Context manager handling the ASGI lifespan."""
        async with AsyncExitStack() as exit_stack:
            for hook in self.on_shutdown[::-1]:
                exit_stack.push_async_callback(
                    functools.partial(self._call_lifespan_hook, hook)
                )

            for manager in self._lifespan_managers:
                if not isinstance(manager, AbstractAsyncContextManager):
                    manager = manager(self)
                await exit_stack.enter_async_context(manager)

            for hook in self.on_startup:
                await self._call_lifespan_hook(hook)

            yield

    async def _call_lifespan_hook(self, hook: LifespanHook) -> None:
        res = await hook(self) if inspect.signature(hook).parameters else hook()
        if is_async_callable(hook):
            await res

    def _create_asgi_handler(self) -> ASGIAppType:
        asgi_handler = wrap_in_exception_handler(app=self.asgi_router)

        return asgi_handler

    def _wrap_send(self, send: Send, scope: Scope) -> Send:
        if self.before_send:

            async def wrapped_send(message: Message) -> None:
                for hook in self.before_send:
                    await hook(message, scope)
                await send(message)

            return wrapped_send
        return send

    def _build_routes(
        self,
        route_handlers: Iterable[BaseRouteHandler],
    ) -> list[HTTPRoute | ASGIRoute | WebSocketRoute]:
        routes = []
        http_path_groups = collections.defaultdict(list)

        for handler in route_handlers:
            if isinstance(handler, HTTPRouteHandler):
                for path in handler.paths:
                    http_path_groups[path].append(handler)
            elif isinstance(handler, ASGIRouteHandler):
                for path in handler.paths:
                    routes.append(ASGIRoute(path=path, route_handler=handler))

        return routes

    def _reduce_handlers(
        self, handlers: Iterable[ControllerRouterHandler]
    ) -> Iterable[BaseRouteHandler]:
        for handler, bases in self._iter_handlers(handlers, bases=[self]):
            yield handler.merge(*bases)

    def _iter_handlers(
        self,
        handlers: Iterable[ControllerRouterHandler],
        bases: list[Router],
    ) -> Iterable[tuple[BaseRouteHandler, list[Router]]]:
        for handler in handlers:
            handler = self._validate_registration_value(handler)
            if isinstance(handler, Router):
                yield from self._iter_handlers(
                    handler.route_handlers, bases=[handler, *bases]
                )
            else:
                yield handler, bases

    def _validate_registration_value(
        self, value: ControllerRouterHandler
    ) -> RouteHandlerType | Router:
        if isinstance(value, Router):
            if value in self:
                raise ImproperlyConfiguredException(
                    "Cannot register a router on itself"
                )

            return value

        if isinstance(
            value, (ASGIRouteHandler, HTTPRouteHandler, WebsocketRouteHandler)
        ):
            return value

        raise ImproperlyConfiguredException(
            "Unsupported value passed to `Router.register`. "
            "If you passed in a function or method, "
            "make sure to decorate it first with one of the routing decorators",
        )


def _create_route_handler_method_map(
    routes: Sequence[HTTPRoute | ASGIRoute | WebSocketRoute],
) -> dict[str, RouteHanderMapItem]:
    route_map = collections.defaultdict(dict)
    for route in routes:
        if isinstance(route, HTTPRoute):
            route_map[route.path] = route.route_handler_map
        else:
            route_map[route.path][
                "websocket" if isinstance(route, WebSocketRoute) else "asgi"
            ] = route.route_handler
    return route_map
