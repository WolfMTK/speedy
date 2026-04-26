from collections.abc import Callable, Awaitable
from contextlib import AbstractAsyncContextManager
from typing import Sequence
from typing import TypeAlias, Any, TYPE_CHECKING, TypeVar

from speedy.types.asgi_types import ASGIApp

if TYPE_CHECKING:
    from speedy.response.base import Response
    from speedy.connection.request import Request
    from speedy.types import Scope, Message
    from speedy.protocols import ILogger
    from speedy.types.helper_types import SyncOrAsyncUnion
    from speedy.handlers.http_handlers.base import HTTPRouteHandler

AfterExceptionHookHandler: TypeAlias = "Callable[[ExceptionT, Scope], SyncOrAsyncUnion[None]]"

# Request hook
AsyncAfterRequestHookHandler: TypeAlias = (
    "Callable[[ASGIApp], Awaitable[ASGIApp]] | Callable[[Response], Awaitable[Response]]"
)

SyncAfterRequestHookHandler: TypeAlias = "Callable[[ASGIApp], ASGIApp] | Callable[[Response], Response]"

AfterRequestHookHandler: TypeAlias = "AsyncAfterRequestHookHandler | SyncAfterRequestHookHandler"

# Response hook
AsyncAfterResponseHookHandler: TypeAlias = "Callable[[Request], Awaitable[None]]"

SyncAfterResponseHookHandler: TypeAlias = "Callable[[Request], None]"

AfterResponseHookHandler: TypeAlias = "AsyncAfterResponseHookHandler | SyncAfterResponseHookHandler"

AsyncBeforeRequestHookHandler: TypeAlias = "Callable[[Request], Awaitable[Any]]"

BeforeRequestHookHandler: TypeAlias = "Callable[[Request], Any | Awaitable[Any]]"

BeforeMessageSendHookHandler: TypeAlias = "Callable[[Message, Scope], SyncOrAsyncUnion[None]]"

Serializer: TypeAlias = Callable[[Any], Any]

AsyncAnyCallable: TypeAlias = Callable[..., Awaitable[Any]]

ExceptionT = TypeVar("ExceptionT", bound=Exception)

ExceptionHandler: TypeAlias = "Callable[[Request, ExceptionT], Response]"

ExceptionLoggingHandler: TypeAlias = "Callable[[ILogger, Scope, list[str]], None]"

GetLogger: TypeAlias = "Callable[..., ILogger]"

Lifespan: TypeAlias = "Sequence[Callable[[ASGIApp], AbstractAsyncContextManager] | AbstractAsyncContextManager] | None"

LifespanHook: TypeAlias = "Callable[[ASGIApp], SyncOrAsyncUnion[Any]] | Callable[[], SyncOrAsyncUnion[Any]]"

AnyCallable: TypeAlias = Callable[..., Any]

HTTPHandlerDecorator: TypeAlias = "Callable[..., Callable[[AnyCallable], HTTPRouteHandler]]"
