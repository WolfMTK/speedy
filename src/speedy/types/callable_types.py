from collections.abc import Callable, Awaitable
from typing import TypeAlias, Any, TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from speedy.protocols.app import ASGIApplication
    from speedy.response.base import Response
    from speedy.connection.request import Request
    from speedy.types import Scope, Message
    from .helper_types import SyncOrAsyncUnion

AfterExceptionHookHandler: TypeAlias = "Callable[[ExceptionT, Scope], SyncOrAsyncUnion[None]]"

# Request hook
AsyncAfterRequestHookHandler: TypeAlias = (
    "Callable[[ASGIApplication], Awaitable[ASGIApplication]] | Callable[[Response], Awaitable[Response]]"
)

SyncAfterRequestHookHandler: TypeAlias = "Callable[[ASGIApplication], ASGIApplication] | Callable[[Response], Response]"

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
