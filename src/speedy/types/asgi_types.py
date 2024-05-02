from typing import (
    Union,
    Literal,
    TypedDict,
    Iterable,
    NotRequired,
    Any,
    Callable,
    Awaitable,
)

from speedy.enums import HttpMethod, ScopeType

type Method = Union[
    Literal[
        'GET',
        'POST',
        'DELETE',
        'PATCH',
        'PUT',
        'HEAD',
        'TRACE',
        'OPTIONS'
    ],
    HttpMethod
]


class ASGIVersions(TypedDict):
    """ ASGI spec version. """

    spec_version: str
    version: Literal['2.0'] | Literal['3.0']


class BaseScope(TypedDict):
    """ Base ASGI-scope. """

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
    """ HTTP-ASGI-scope. """

    type: Literal[ScopeType.HTTP]
    method: Method


class WebSocketScope(BaseScope):
    """ WebSocket-ASGI-scope. """

    type: Literal[ScopeType.WEBSOCKET]
    subprotocols: Iterable[str]


class LifespanScope(TypedDict):
    """ Lifespan-ASGI-scope. """

    type: Literal['lifespan']
    asgi: ASGIVersions
    state: NotRequired[dict[str, Any]]


class HTTPRequestEvent(TypedDict):
    """ ASGI `http.request` event. """

    type: Literal['http.request']
    body: bytes
    more_body: bool


class HTTPDisconnectEvent(TypedDict):
    """ ASGI `http.disconnect` event. """

    type: Literal['http.disconnect']


class WebSocketConnectEvent(TypedDict):
    """ ASGI `websocket.connect` event. """

    type: Literal['websocket.connect']


class _WebSocketReceiveEventBytes(TypedDict):
    """ ASGI `websocket.receive` event. """

    type: Literal['websocket.receive']
    bytes: bytes
    text: NotRequired[None]


class _WebSocketReceiveEventText(TypedDict):
    """ ASGI `websocket.receive` event. """

    type: Literal['websocket.receive']
    bytes: NotRequired[None]
    text: str


class WebSocketDisconnectEvent(TypedDict):
    """ ASGI `websocket.receive` event. """

    type: Literal['websocket.disconnect']
    code: int


class LifespanStartupEvent(TypedDict):
    """ ASGI `lifespan.startup` event. """

    type: Literal['lifespan.startup']


class LifespanShutdownEvent(TypedDict):
    """ ASGI `lifespan.shutdown` event. """

    type: Literal['lifespan.shutdown']


class HTTPResponseStartEvent(TypedDict):
    """ ASGI `http.response.start` event. """

    type: Literal['http.response.start']
    status: int
    headers: NotRequired[Iterable[tuple[bytes, bytes]]]
    trailers: NotRequired[bool]


class HTTPResponseBodyEvent(TypedDict):
    """ ASGI `http.response.body` event. """

    type: Literal['http.response.body']
    body: bytes
    more_body: NotRequired[bool]


class HTTPResponseTrailersEvent(TypedDict):
    """ ASGI `http.response.trailers` event. """

    type: Literal['http.response.trailers']
    headers: Iterable[tuple[bytes, bytes]]
    more_trailers: bool


class HTTPServerPushEvent(TypedDict):
    """ ASGI `http.response.push` event. """

    type: Literal['http.response.push']
    path: str
    headers: Iterable[tuple[bytes, bytes]]


class WebSocketAcceptEvent(TypedDict):
    """ ASGI `websocket.accept` event. """

    type: Literal['websocket.accept']
    subprotocol: NotRequired[str | None]
    headers: NotRequired[Iterable[tuple[bytes, bytes]]]


class _WebSocketSendEventBytes(TypedDict):
    type: Literal['websocket.send']
    bytes: bytes
    text: NotRequired[None]


class _WebSocketSendEventText(TypedDict):
    type: Literal['websocket.send']
    bytes: NotRequired[None]
    text: str


class WebSocketResponseStartEvent(TypedDict):
    """ ASGI `websocket.http.response.start` event. """

    type: Literal['websocket.http.response.start']
    status: int
    headers: Iterable[tuple[bytes, bytes]]


class WebSocketResponseBodyEvent(TypedDict):
    """ ASGI `websocket.http.response.body` event. """

    type: Literal['websocket.http.response.body']
    body: bytes
    more_body: NotRequired[bool]


class WebSocketCloseEvent(TypedDict):
    """ ASGI `websocket.close` event. """

    type: Literal['websocket.close']
    code: NotRequired[int]
    reason: NotRequired[str | None]


class LifespanStartupCompleteEvent(TypedDict):
    """ ASGI `lifespan.startup.complete` event. """

    type: Literal['lifespan.startup.complete']


class LifespanStartupFailedEvent(TypedDict):
    """ ASGI `lifespan.startup.failed` event. """

    type: Literal['lifespan.startup.failed']
    message: str


class LifespanShutdownCompleteEvent(TypedDict):
    """ ASGI `lifespan.shutdown.complete` event. """

    type: Literal['lifespan.shutdown.complete']


class LifespanShutdownFailedEvent(TypedDict):
    """ ASGI `lifespan.shutdown.failed` event. """

    type: Literal['lifespan.shutdown.failed']
    message: str


type WebSocketReceiveEvent = Union[
    _WebSocketReceiveEventBytes,
    _WebSocketReceiveEventText
]

type WebSocketSendEvent = Union[
    _WebSocketSendEventBytes,
    _WebSocketSendEventText
]

type HTTPReceiveMessage = Union[
    HTTPRequestEvent,
    HTTPDisconnectEvent
]

type WebSocketReceiveMessage = Union[
    WebSocketConnectEvent,
    WebSocketReceiveEvent,
    WebSocketDisconnectEvent
]

type LifeSpanReceiveMessage = Union[
    LifespanStartupEvent,
    LifespanShutdownEvent
]

type Scope = Union[HttpScope, WebSocketScope, LifespanScope]

type Message = Union[HTTPReceiveMessage, WebSocketReceiveMessage]

type ASGIReceiveEvent = Union[
    HTTPReceiveMessage,
    WebSocketReceiveMessage,
    LifeSpanReceiveMessage
]

type ASGIReceiveCallable = Callable[[], Awaitable[ASGIReceiveEvent]]

type HTTPSendMessage = Union[
    HTTPResponseStartEvent,
    HTTPResponseBodyEvent,
    HTTPResponseTrailersEvent,
    HTTPServerPushEvent,
    HTTPDisconnectEvent
]

type WebSocketSendMessage = Union[
    WebSocketAcceptEvent,
    WebSocketSendEvent,
    WebSocketResponseStartEvent,
    WebSocketResponseBodyEvent,
    WebSocketCloseEvent
]

type LifeSpanSendMessage = Union[
    LifespanStartupCompleteEvent,
    LifespanStartupFailedEvent,
    LifespanShutdownCompleteEvent,
    LifespanShutdownFailedEvent
]

type ASGISendEvent = Union[
    HTTPSendMessage,
    WebSocketSendMessage,
    LifeSpanSendMessage
]

type ASGISendCallable = Callable[[ASGISendEvent], Awaitable[None]]
