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
