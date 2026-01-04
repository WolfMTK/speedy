from __future__ import annotations

from typing import Sequence, Mapping, Any, TYPE_CHECKING


from speedy.datastructures import ETag
from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.handlers.base import BaseRouteHandler
from speedy.handlers.http_handlers.helpers import normalize_http_method
from speedy.response import Response
from speedy.types import (
    AnyCallable,
    AfterRequestHookHandler,
    AfterResponseHookHandler,
    ExceptionHandlersMap,
    Method,
    Middleware,
    ResponseCookies,
    ResponseHeaders,
    TypeDecodersSequence,
    TypeEncodersMap,
    ParametersMap,
)

if TYPE_CHECKING:
    from speedy import BackgroundTask, BackgroundTasks, MediaType
    from speedy.connection import Request


class HTTPRouteHandler(BaseRouteHandler):
    def __init__(
            self,
            path: str | Sequence[str] | None = None,
            *,
            fn: AnyCallable,
            http_method: Method | Sequence[Method],
            after_request: AfterRequestHookHandler | None = None,
            after_response: AfterResponseHookHandler | None = None,
            background: BackgroundTask | BackgroundTasks | None = None,
            etag: ETag | None = None,
            exception_handlers: ExceptionHandlersMap | None = None,
            media_type: MediaType | None = None,
            middleware: Sequence[Middleware] | None = None,
            name: str | None = None,
            opt: Mapping[str, Any] | None = None,
            request_class: type[Request] | None = None,
            request_max_body_size: int | None = None,
            response_class: type[Response] | None = None,
            response_cookies: ResponseCookies | None = None,
            response_headers: ResponseHeaders | None = None,
            staus_code: int | None = None,
            tags: Sequence[str] | None = None,
            type_decoders: TypeDecodersSequence | None = None,
            type_encoders: TypeEncodersMap | None = None,
            signature_namespace: Mapping[str, Any] | None = None,
            parameters: ParametersMap | None = None,
            **kwargs: Any
    ) -> None:
        if not http_method:
            raise ImproperlyConfiguredException("An `http_method` must be provided.")

        self.http_methods = normalize_http_method(http_methods=http_method)
        self.status_code = staus_code

        super().__init__(
            path,
            fn=fn,
            exception_handlers=exception_handlers,
            middleware=middleware,
            name=name,
            opt=opt,
            signature_namespace=signature_namespace,
            parameters=parameters,
            type_decoders=type_decoders,
            type_encoders=type_encoders,
            **kwargs,
        )
