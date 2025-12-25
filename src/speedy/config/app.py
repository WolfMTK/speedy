from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING, Callable

from speedy.constants import MULTIPART_FORM_PART_LIMIT
from speedy.datastructures import ETag, State
from speedy.types import (
    AfterExceptionHookHandler,
    AfterRequestHookHandler,
    AfterResponseHookHandler,
    BeforeRequestHookHandler,
    BeforeMessageSendHookHandler,
    ExceptionHandlersMap,
    Middleware,
    ParametersMap,
    Empty,
    EmptyType,
    ResponseCookies,
    ResponseHeaders,
    ControllerRouterHandler,
    TypeDecodersSequence,
    TypeEncodersMap, LifespanHook,
)

if TYPE_CHECKING:
    from speedy import Speedy
    from speedy.connection import Request, WebSocket
    from speedy.response import Response
    from speedy.config import BaseLoggingConfig


@dataclass(slots=True)
class ApplicationConfig:
    after_exception: list[AfterExceptionHookHandler] = field(default_factory=list)
    after_request: AfterRequestHookHandler | None = field(default=None)
    after_response: AfterResponseHookHandler | None = field(default=None)
    allowed_hosts: list[str] | None = field(default=None)
    before_request: BeforeRequestHookHandler | None = field(default=None)
    before_send: list[BeforeMessageSendHookHandler] = field(default_factory=list)
    debug: bool = field(default=False)
    etag: ETag | None = field(default=None)
    exception_handlers: ExceptionHandlersMap = field(default_factory=dict)
    logging_config: BaseLoggingConfig | None = field(default=None)
    middleware: list[Middleware] = field(default_factory=list)
    multipart_form_part_limit: int = field(default=MULTIPART_FORM_PART_LIMIT)
    on_shutdown: list[LifespanHook] = field(default_factory=list)
    on_startup: list[LifespanHook] = field(default_factory=list)
    opt: dict[str, Any] = field(default_factory=dict)
    parameters: ParametersMap = field(default_factory=dict)
    path: str = field(default="")
    request_class: type[Request] | None = field(default=None)
    request_max_body_size: int | None | EmptyType = Empty
    response_class: type[Response] | None = field(default=None)
    response_cookies: ResponseCookies = field(default_factory=list)
    response_headers: ResponseHeaders = field(default_factory=list)
    lifespan: list[Callable[[Speedy], AbstractAsyncContextManager] | AbstractAsyncContextManager] = field(
        default_factory=list,
    )
    route_handlers: list[ControllerRouterHandler] = field(default_factory=list)
    signature_namespace: dict[str, Any] = field(default_factory=dict)
    signature_types: list[Any] = field(default_factory=list)
    state: State = field(default_factory=State)
    tags: list[str] = field(default_factory=list)
    type_decoders: TypeDecodersSequence | None = field(default=None)
    type_encoders: TypeEncodersMap | None = field(default=None)
    websocket_class: type[WebSocket] = field(default=None)
