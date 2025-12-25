from __future__ import annotations

import functools
import inspect
import logging
import os
from contextlib import asynccontextmanager, AsyncExitStack, AbstractAsyncContextManager
from typing import Sequence, Mapping, Any, TYPE_CHECKING, AsyncGenerator

from speedy import Router
from speedy._asgi import ASGIRouter
from speedy.config import ApplicationConfig, BaseLoggingConfig, LoggingConfig
from speedy.config.logging import get_logger_placeholder
from speedy.connection import Request, WebSocket
from speedy.constants import MULTIPART_FORM_PART_LIMIT, REQUEST_MAX_BODY_SIZE
from speedy.datastructures import ETag, State
from speedy.protocols import ILogger
from speedy.types import (
    ControllerRouterHandler,
    AfterExceptionHookHandler,
    AfterRequestHookHandler,
    AfterResponseHookHandler,
    BeforeRequestHookHandler,
    BeforeMessageSendHookHandler,
    ExceptionHandlersMap,
    ParametersMap,
    ResponseCookies,
    ResponseHeaders,
    TypeDecodersSequence,
    TypeEncodersMap,
    Scope,
    Middleware,
    EmptyType,
    Empty,
    GetLogger,
    LifespanScope,
    Receive,
    LifeSpanReceive,
    LifeSpanSend,
    Send,
    Lifespan,
    LifespanHook,
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
            allowed_hosts: Sequence[str] | None = None,
            before_request: BeforeRequestHookHandler | None = None,
            before_send: Sequence[BeforeMessageSendHookHandler] | None = None,
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

        config = ApplicationConfig(
            after_exception=list(after_exception or []),
            after_request=after_request,
            after_response=after_response,
            allowed_hosts=list(allowed_hosts or []),
            before_request=before_request,
            before_send=list(before_send or []),
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

        self.get_logger: GetLogger = get_logger_placeholder
        self.logger: ILogger | None = None

        self.after_exception = [ensure_async_callable(header) for header in config.after_exception]
        self.allowed_hosts = config.allowed_hosts
        self.before_send = [ensure_async_callable(header) for header in config.before_send]
        self.logging_config = config.logging_config
        self.request_class: type[Request] = config.request_class or Request
        self.state = config.state
        self.websocket_class: type[WebSocket] = config.websocket_class or WebSocket
        self.on_startup = config.on_startup
        self.on_shutdown = config.on_shutdown

        self._debug: bool = config.debug
        self._lifespan_managers = config.lifespan

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

        if self.logging_config:
            self.get_logger = self.logging_config.configure()
            self.logger = self.get_logger("speedy")

    async def __call__(
            self,
            scope: Scope | LifespanScope,
            receive: Receive | LifeSpanReceive,
            send: Send | LifeSpanSend,
    ) -> None:
        if scope["type"] == "lifespan":
            await self.asgi_router.lifespan(receive, send)

    @property
    def debug(self) -> bool:
        return self._debug

    @debug.setter
    def debug(self, value: bool) -> None:
        if self.logger and self.logging_config:
            self.logging_config.set_level(self.logger, logging.DEBUG if value else logging.INFO)
        self._debug = value

    @asynccontextmanager
    async def lifespan(self) -> AsyncGenerator[None, None]:
        """ Context manager handling the ASGI lifespan. """
        async with AsyncExitStack() as exit_stack:
            for hook in self.on_shutdown[::-1]:
                exit_stack.push_async_callback(functools.partial(self._call_lifespan_hook, hook))

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
