from typing import Literal, TypedDict, Iterable, NotRequired, Any

from speedy.enums import HTTPMethod, ScopeType

type HTTPMethodName = Literal["GET", "POST", "DELETE", "PATCH", "PUT", "HEAD", "TRACE", "OPTIONS"]

type Method = HTTPMethodName | HTTPMethod

Version = Literal["2.0"] | Literal["3.0"]

Headers = Iterable[tuple[bytes, bytes]]


class ASGIVersion(TypedDict):
    """ASGI spec version."""
    spec_version: str
    version: Version


class HTTPScope(TypedDict):
    """HTTP-ASGI scope."""
    type: Literal[ScopeType.HTTP]
    asgi: ASGIVersion
    http_version: str
    method: str | Method
    scheme: str
    path: str
    raw_path: bytes
    query_string: bytes
    root_path: str
    headers: Headers
    client: tuple[str, int] | None
    server: tuple[str, int | None] | None
    state: NotRequired[dict[str, Any,]]
    extensions: NotRequired[dict[str, dict[object, object]]]


class WebSocketScope(TypedDict):
    """WebSocket-ASGI scope."""
    type: Literal[ScopeType.WEBSOCKET]
    asgi: ASGIVersion
    http_version: str
    scheme: str
    path: str
    raw_path: bytes
    query_string: bytes
    root_path: str
    headers: Headers
    client: tuple[str, int] | None
    server: tuple[str, int | None] | None
    subprotocols: Iterable[str]
    state: NotRequired[dict[str, Any,]]
    extensions: NotRequired[dict[str, dict[object, object]]]


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
    headers: Headers
    trailers: bool


class HTTPResponseBodyEvent(TypedDict):
    """ASGI `http.response.body` event."""
    type: Literal["http.response.body"]
    body: bytes
    more_body: bool


class HTTPResponseTrailersEvent(TypedDict):
    """ASGI `http.response.trailers` event."""
    type: Literal["http.response.trailers"]
    headers: Headers
    more_trailers: bool


class HTTPResponsePathsendEvent(TypedDict):
    """ASGI `http.response.pathsend` event."""
    type: Literal["http.response.pathsend"]
    path: str


class HTTPServerPushEvent(TypedDict):
    """ASGI `http.response.push` event."""
    type: Literal["http.response.push"]
    path: str
    headers: Headers


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
    headers: Headers


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
    headers: Headers


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
