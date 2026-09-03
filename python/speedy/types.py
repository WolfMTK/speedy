from contextlib import AbstractAsyncContextManager
from typing import Literal, TypedDict, Iterable, NotRequired, Any, Union, Callable, Awaitable, MutableMapping, Sequence

from speedy.enums import HTTPMethod, ScopeType
from speedy.protocols import IRequest, IResponse

type HTTPMethodName = Literal["GET", "POST", "DELETE", "PATCH", "PUT", "HEAD", "TRACE", "OPTIONS"]

type Method = HTTPMethodName | HTTPMethod

type Version = Literal["2.0"] | Literal["3.0"]

type HeadersT = Iterable[tuple[bytes, bytes]]

type ClientT = tuple[str, int] | None

type ServerT = tuple[str, int | None] | None


class ASGIVersion(TypedDict):
    """ASGI spec version."""
    spec_version: str
    version: Version


class BaseScope(TypedDict):
    """Base scope."""
    app: "ASGIApplication"
    asgi: ASGIVersion
    http_version: str
    scheme: str
    path: str
    raw_path: bytes
    query_string: bytes
    root_path: str
    headers: HeadersT
    client: ClientT
    server: ServerT
    state: NotRequired[dict[str, Any]]
    extensions: NotRequired[dict[str, dict[object, object]]]


class HTTPScope(BaseScope):
    """HTTP-ASGI scope."""
    type: Literal[ScopeType.HTTP]
    method: str | Method


class WebSocketScope(BaseScope):
    """WebSocket-ASGI scope."""
    type: Literal[ScopeType.WEBSOCKET]
    subprotocols: Iterable[str]


class LifespanScope(TypedDict):
    """Lifespan-ASGI scope."""
    type: Literal[ScopeType.LIFESPAN]
    asgi: ASGIVersion
    state: NotRequired[dict[str, Any]]


type Scope = HTTPScope | WebSocketScope | LifespanScope


class HTTPRequestEvent(TypedDict):
    """ASGI `http.request` event."""
    type: Literal["http.request"]
    body: bytes
    more_body: bool


class HTTPResponseDebugEvent(TypedDict):
    """ASGI `http.response.debug` event."""
    type: Literal["http.response.debug"]
    info: dict[str, object]


class HTTPResponseStartEvent(TypedDict):
    """ASGI `http.response.start` event."""
    type: Literal["http.response.start"]
    status: int
    headers: HeadersT
    trailers: bool


class HTTPResponseBodyEvent(TypedDict):
    """ASGI `http.response.body` event."""
    type: Literal["http.response.body"]
    body: bytes
    more_body: bool


class HTTPResponseTrailersEvent(TypedDict):
    """ASGI `http.response.trailers` event."""
    type: Literal["http.response.trailers"]
    headers: HeadersT
    more_trailers: bool


class HTTPResponsePathsendEvent(TypedDict):
    """ASGI `http.response.pathsend` event."""
    type: Literal["http.response.pathsend"]
    path: str


class HTTPServerPushEvent(TypedDict):
    """ASGI `http.response.push` event."""
    type: Literal["http.response.push"]
    path: str
    headers: HeadersT


class HTTPDisconnectEvent(TypedDict):
    """ASGI `http.disconnect` event."""
    type: Literal["http.disconnect"]


class WebSocketConnectEvent(TypedDict):
    """ASGI `websocket.connect` event."""
    type: Literal["websocket.connect"]


class WebSocketAcceptEvent(TypedDict):
    """ASGI `websocket.accept` event."""
    type: Literal["websocket.accept"]
    subprotocol: str | None
    headers: HeadersT


class WebSocketReceiveEvent(TypedDict):
    """ASGI `websocket.receive` event."""
    type: Literal["websocket.receive"]
    bytes: bytes | None
    text: str | None


class WebSocketSendEvent(TypedDict):
    """ASGI `websocket.send` event."""
    type: Literal["websocket.send"]
    bytes: bytes | None
    text: str | None


class WebSocketResponseStartEvent(TypedDict):
    """ASGI `websocket.http.response.start` event."""
    type: Literal["websocket.http.response.start"]
    status: int
    headers: HeadersT


class WebSocketResponseBodyEvent(TypedDict):
    """ASGI `websocket.http.response.body` event."""
    type: Literal["websocket.http.response.body"]
    body: bytes
    more_body: bool


class WebSocketDisconnectEvent(TypedDict):
    """ASGI `websocket.disconnect` event."""
    type: Literal["websocket.disconnect"]
    code: int
    reason: str | None


class WebSocketCloseEvent(TypedDict):
    """ASGI `websocket.close` event."""
    type: Literal["websocket.close"]
    code: int
    reason: str | None


class LifespanStartupEvent(TypedDict):
    """ASGI `lifespan.startup` event."""
    type: Literal["lifespan.startup"]


class LifespanShutdownEvent(TypedDict):
    """ASGI `lifespan.shutdown` event."""
    type: Literal["lifespan.shutdown"]


class LifespanStartupCompleteEvent(TypedDict):
    """ASGI `lifespan.startup.complete` event."""
    type: Literal["lifespan.startup.complete"]


class LifespanStartupFailedEvent(TypedDict):
    """ASGI `lifespan.startup.failed"` event."""
    type: Literal["lifespan.startup.failed"]
    message: str


class LifespanShutdownCompleteEvent(TypedDict):
    """ASGI `lifespan.shutdown.complete` event."""
    type: Literal["lifespan.shutdown.complete"]


class LifespanShutdownFailedEvent(TypedDict):
    """ASGI `lifespan.shutdown.failed` event."""
    type: Literal["lifespan.shutdown.failed"]
    message: str


type ReceiveMessage = Union[
    HTTPRequestEvent,
    HTTPDisconnectEvent,
    WebSocketConnectEvent,
    WebSocketReceiveEvent,
    WebSocketDisconnectEvent,
    LifespanStartupEvent,
    LifespanShutdownEvent,
]

type Message = Union[
    HTTPResponseStartEvent,
    HTTPResponseBodyEvent,
    HTTPResponseTrailersEvent,
    HTTPServerPushEvent,
    HTTPDisconnectEvent,
    WebSocketAcceptEvent,
    WebSocketSendEvent,
    WebSocketResponseStartEvent,
    WebSocketResponseBodyEvent,
    WebSocketCloseEvent,
    LifespanStartupCompleteEvent,
    LifespanStartupFailedEvent,
    LifespanShutdownCompleteEvent,
    LifespanShutdownFailedEvent,
]

type Receive = Callable[[], Awaitable[ReceiveMessage]]

type Send = Callable[[Message], Awaitable[None]]

type ASGIApplication = Callable[
    [
        Scope,
        Receive,
        Send,
    ],
    Awaitable[None],
]

type Middleware = Callable[..., ASGIApplication]

type HTTPExceptionHandler = Callable[[IRequest, Exception], IResponse]

type ExceptionHandlersMap = MutableMapping[int | type[Exception], HTTPExceptionHandler]

type Lifespan = Sequence[Callable[[ASGIApplication], AbstractAsyncContextManager] | AbstractAsyncContextManager]
