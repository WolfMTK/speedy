from typing import (
    TypeAlias,
    Union,
    Literal,
    TypedDict,
    Iterable,
    NotRequired, Any
)

from speedy import HttpMethod, ScopeType

Method: TypeAlias = Union[
    Literal['GET', 'POST', 'DELETE', 'PATCH', 'PUT', 'HEAD', 'TRACE', 'OPTIONS'],
    HttpMethod
]


class ASGIVersions(TypedDict):
    """ASGI spec version."""

    spec_version: str
    version: Literal['2.0'] | Literal['3.0']


class BaseScope(TypedDict):
    """Base ASGI-scope."""

    asgi: ASGIVersions
    http_version: str
    scheme: str
    path: str
    raw_path: bytes
    query_string: bytes
    root_path: str
    headers: Iterable[tuple[bytes, bytes]]
    client: tuple[str, int] | None
    server: tuple[str, int | None] | None
    state: NotRequired[dict[str, Any]]
    extensions: NotRequired[dict[str, dict[object, object]]]


class HttpScope(BaseScope):
    """HTTP-ASGI-scope."""

    type: Literal[ScopeType.HTTP]
    method: Method


class WebSocketScope(BaseScope):
    """WebSocket-ASGI-scope."""
    type: Literal[ScopeType.WEBSOCKET]
    subprotocols: Iterable[str]
