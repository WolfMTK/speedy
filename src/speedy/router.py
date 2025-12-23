from __future__ import annotations

from typing import Sequence, Mapping, Any

from speedy._layers.utils import narrow_response_cookies, narrow_response_headers
from speedy.connection import Request, WebSocket
from speedy.datastructures import ETag
from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.response import Response
from speedy.types import (
    AfterRequestHookHandler,
    AfterResponseHookHandler,
    BeforeRequestHookHandler,
    ExceptionHandlersMap,
    Middleware,
    ParametersMap,
    ResponseCookies,
    ResponseHeaders,
    ControllerRouterHandler,
    TypeDecodersSequence,
    TypeEncodersMap,
    EmptyType,
    Empty,
    AsyncAfterRequestHookHandler,
    AsyncAfterResponseHookHandler,
    AsyncBeforeRequestHookHandler,

)
from speedy.utils.path import normalize_path
from speedy.utils.signature import add_types_to_signature_namespace
from speedy.utils.sync import ensure_async_callable


class Router:
    """ The Speedy Router class. """

    def __init__(
            self,
            path: str,
            *,
            after_request: AfterRequestHookHandler | None = None,
            after_response: AfterResponseHookHandler | None = None,
            before_request: BeforeRequestHookHandler | None = None,
            etag: ETag | None = None,
            exception_handlers: ExceptionHandlersMap | None = None,
            middleware: Sequence[Middleware] | None = None,
            opt: Mapping[str, Any,] | None = None,
            parameters: ParametersMap | None = None,
            request_class: type[Request] | None = None,
            response_class: type[Response] | None = None,
            response_cookies: ResponseCookies | None = None,
            response_headers: ResponseHeaders | None = None,
            route_handlers: Sequence[ControllerRouterHandler],
            signature_namespace: Mapping[str, Any] | None = None,
            signature_types: Sequence[Any] | None = None,
            tags: Sequence[str] | None = None,
            type_decoders: TypeDecodersSequence | None = None,
            type_encoders: TypeEncodersMap | None = None,
            websocket_class: type[WebSocket] | None = None,
            request_max_body_size: int | None | EmptyType = Empty,
    ) -> None:
        self.after_request: AsyncAfterRequestHookHandler | None = (
            ensure_async_callable(after_request) if after_request else None
        )
        self.after_response: AsyncAfterResponseHookHandler | None = (
            ensure_async_callable(after_response) if after_response else None
        )
        self.before_request: AsyncBeforeRequestHookHandler | None = ensure_async_callable(
            before_request) if before_request else None
        self.etag = etag
        self.exception_handlers = dict(exception_handlers or {})
        self.middleware = list(middleware or [])
        self.opt = dict(opt or {})
        self.parameters = dict(parameters or {})
        self.path = normalize_path(path)
        self.request_class = request_class
        self.response_class = response_class
        self.response_cookies = narrow_response_cookies(response_cookies) if response_cookies else ()
        self.response_headers = narrow_response_headers(response_headers) if response_headers else ()
        self.signature_namespace = add_types_to_signature_namespace(
            signature_types or [], dict(signature_namespace or {})
        )
        self.tags = list(tags or [])
        self.registered_route_handler_ids: set[int] = set()
        self.type_encoders = dict(type_encoders) if type_encoders is not None else {}
        self.type_decoders = list(type_decoders) if type_decoders is not None else list()
        self.websocket_class = websocket_class
        self.request_max_body_size = request_max_body_size

        self.route_handlers = tuple(route_handlers)

    def register(self, value: ControllerRouterHandler) -> None:
        """ Register a Route instance or RouteHandler on the router. """
        if value is self:
            raise ImproperlyConfiguredException("Cannot register a router on itself")
        self.route_handlers = (*self.route_handlers, value)
