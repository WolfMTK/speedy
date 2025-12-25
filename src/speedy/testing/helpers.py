from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Sequence, TYPE_CHECKING, Any, Mapping, Callable

from speedy import Speedy
from speedy.constants import MULTIPART_FORM_PART_LIMIT
from speedy.datastructures import ETag, State
from speedy.middleware.session.base import BaseBackendConfig
from speedy.testing.client import TestClient, AsyncTestClient
from speedy.types import (
    ControllerRouterHandler,
    AfterExceptionHookHandler,
    AfterRequestHookHandler,
    AfterResponseHookHandler,
    BeforeRequestHookHandler,
    BeforeMessageSendHookHandler,
    ExceptionHandlersMap,
    Middleware,
    ParametersMap,
    ResponseCookies,
    ResponseHeaders,
    TypeEncodersMap,
    AnyIOBackend,
    LifespanHook,
)

if TYPE_CHECKING:
    from speedy.connection import Request, WebSocket
    from speedy.response import Response


def create_test_client(
        route_handlers: ControllerRouterHandler | Sequence[ControllerRouterHandler] | None = None,
        *,
        after_exception: Sequence[AfterExceptionHookHandler] | None = None,
        after_request: AfterRequestHookHandler | None = None,
        after_response: AfterResponseHookHandler | None = None,
        allowed_hosts: Sequence[str] | None = None,
        backend: AnyIOBackend = "asyncio",
        backend_options: dict[str, Any] | None = None,
        base_url: str = "http://testserver.local",
        before_request: BeforeRequestHookHandler | None = None,
        before_send: Sequence[BeforeMessageSendHookHandler] | None = None,
        debug: bool = True,
        etag: ETag | None = None,
        exception_handlers: ExceptionHandlersMap | None = None,
        middleware: Sequence[Middleware] | None = None,
        on_startup: Sequence[LifespanHook] | None = None,
        on_shutdown: Sequence[LifespanHook] | None = None,
        multipart_form_part_limit: int = MULTIPART_FORM_PART_LIMIT,
        opt: Mapping[str, Any] | None = None,
        parameters: ParametersMap | None = None,
        path: str | None = None,
        lifespan: list[Callable[[Speedy], AbstractAsyncContextManager] | AbstractAsyncContextManager] | None = None,
        raise_server_exceptions: bool = True,
        request_class: type[Request] | None = None,
        response_class: type[Response] | None = None,
        response_cookies: ResponseCookies | None = None,
        response_headers: ResponseHeaders | None = None,
        root_path: str = "",
        session_config: BaseBackendConfig | None = None,
        signature_namespace: Mapping[str, Any] | None = None,
        signature_types: Sequence[Any] | None = None,
        state: State | None = None,
        tags: Sequence[str] | None = None,
        timeout: float | None = None,
        type_encoders: TypeEncodersMap | None = None,
        websocket_class: type[WebSocket] | None = None,
) -> TestClient[Speedy]:
    """ Create a Speedy app instance and initializes it. """
    route_handlers = () if route_handlers is None else route_handlers
    if not isinstance(route_handlers, Sequence):
        route_handlers = (route_handlers,)

    app = Speedy(
        after_exception=after_exception,
        after_request=after_request,
        after_response=after_response,
        allowed_hosts=allowed_hosts,
        before_request=before_request,
        before_send=before_send,
        debug=debug,
        etag=etag,
        lifespan=lifespan,
        exception_handlers=exception_handlers,
        middleware=middleware,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        multipart_form_part_limit=multipart_form_part_limit,
        opt=opt,
        parameters=parameters,
        path=path,
        request_class=request_class,
        response_class=response_class,
        response_cookies=response_cookies,
        response_headers=response_headers,
        route_handlers=route_handlers,
        signature_namespace=signature_namespace,
        signature_types=signature_types,
        state=state,
        tags=tags,
        type_encoders=type_encoders,
        websocket_class=websocket_class,
    )

    return TestClient[Speedy](
        app=app,
        backend=backend,
        backend_options=backend_options,
        base_url=base_url,
        raise_server_exceptions=raise_server_exceptions,
        root_path=root_path,
        timeout=timeout,
        session_config=session_config,
    )


def create_async_test_client(
        route_handlers: ControllerRouterHandler | Sequence[ControllerRouterHandler] | None = None,
        *,
        after_exception: Sequence[AfterExceptionHookHandler] | None = None,
        after_request: AfterRequestHookHandler | None = None,
        after_response: AfterResponseHookHandler | None = None,
        allowed_hosts: Sequence[str] | None = None,
        base_url: str = "http://testserver.local",
        before_request: BeforeRequestHookHandler | None = None,
        before_send: Sequence[BeforeMessageSendHookHandler] | None = None,
        debug: bool = True,
        etag: ETag | None = None,
        exception_handlers: ExceptionHandlersMap | None = None,
        middleware: Sequence[Middleware] | None = None,
        multipart_form_part_limit: int = MULTIPART_FORM_PART_LIMIT,
        on_startup: Sequence[LifespanHook] | None = None,
        on_shutdown: Sequence[LifespanHook] | None = None,
        opt: Mapping[str, Any] | None = None,
        parameters: ParametersMap | None = None,
        path: str | None = None,
        lifespan: list[Callable[[Speedy], AbstractAsyncContextManager] | AbstractAsyncContextManager] | None = None,
        raise_server_exceptions: bool = True,
        request_class: type[Request] | None = None,
        response_class: type[Response] | None = None,
        response_cookies: ResponseCookies | None = None,
        response_headers: ResponseHeaders | None = None,
        root_path: str = "",
        signature_namespace: Mapping[str, Any] | None = None,
        signature_types: Sequence[Any] | None = None,
        state: State | None = None,
        tags: Sequence[str] | None = None,
        timeout: float | None = None,
        type_encoders: TypeEncodersMap | None = None,
        websocket_class: type[WebSocket] | None = None,
) -> AsyncTestClient[Speedy]:
    """ Create a Speedy app instance and initializes it. """
    route_handlers = () if route_handlers is None else route_handlers
    if not isinstance(route_handlers, Sequence):
        route_handlers = (route_handlers,)

    app = Speedy(
        after_exception=after_exception,
        after_request=after_request,
        after_response=after_response,
        allowed_hosts=allowed_hosts,
        before_request=before_request,
        before_send=before_send,
        debug=debug,
        etag=etag,
        lifespan=lifespan,
        exception_handlers=exception_handlers,
        middleware=middleware,
        multipart_form_part_limit=multipart_form_part_limit,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        opt=opt,
        parameters=parameters,
        path=path,
        request_class=request_class,
        response_class=response_class,
        response_cookies=response_cookies,
        response_headers=response_headers,
        route_handlers=route_handlers,
        signature_namespace=signature_namespace,
        signature_types=signature_types,
        state=state,
        tags=tags,
        type_encoders=type_encoders,
        websocket_class=websocket_class,
    )

    return AsyncTestClient[Speedy](
        app=app,
        base_url=base_url,
        raise_server_exceptions=raise_server_exceptions,
        root_path=root_path,
        timeout=timeout,
    )
