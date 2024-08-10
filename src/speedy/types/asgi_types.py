"""
Copyright (c) Django Software Foundation and individual contributors.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice,
       this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above copyright
       notice, this list of conditions and the following disclaimer in the
       documentation and/or other materials provided with the distribution.

    3. Neither the name of Django nor the names of its contributors may be used
       to endorse or promote products derived from this software without
       specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
from __future__ import annotations

import sys
from typing import (
    Union,
    Literal,
    TypedDict,
    Iterable,
    Any,
    Callable,
    Awaitable,
    TYPE_CHECKING,
)

from speedy.enums import HttpMethod, ScopeType

if sys.version_info >= (3, 11):
    from typing import NotRequired
else:
    from typing_extensions import NotRequired, TypeAlias

if TYPE_CHECKING:
    from speedy.protocols import ASGIApplication

Method: TypeAlias = Union[Literal['GET', 'POST', 'DELETE', 'PATCH', 'PUT', 'HEAD', 'TRACE', 'OPTIONS'], HttpMethod]

Version = Literal['2.0'] | Literal['3.0']


class ASGIVersions(TypedDict):
    """ ASGI spec version. """

    spec_version: str
    version: Version


class BaseScope(TypedDict):
    """ Base ASGI-scope. """

    app: ASGIApplication  # type: ignore[valid-type]
    asgi: ASGIVersions
    http_version: str
    scheme: str
    path: str
    raw_path: bytes
    query_string: bytes
    root_path: str
    path_params: dict[str, str]
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

    app: ASGIApplication  # type: ignore[valid-type]
    type: Literal[ScopeType.LIFESPAN]
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


WebSocketReceiveEvent: TypeAlias = Union[
    _WebSocketReceiveEventBytes,
    _WebSocketReceiveEventText
]

WebSocketSendEvent: TypeAlias = Union[
    _WebSocketSendEventBytes,
    _WebSocketSendEventText
]

HTTPReceiveMessage: TypeAlias = Union[
    HTTPRequestEvent,
    HTTPDisconnectEvent
]

WebSocketReceiveMessage: TypeAlias = Union[
    WebSocketConnectEvent,
    WebSocketReceiveEvent,
    WebSocketDisconnectEvent
]

LifeSpanReceiveMessage: TypeAlias = Union[
    LifespanStartupEvent,
    LifespanShutdownEvent
]

Scope: TypeAlias = Union[HttpScope, WebSocketScope]

Message: TypeAlias = Union[HTTPReceiveMessage, WebSocketReceiveMessage]

ASGIReceiveEvent: TypeAlias = Union[
    HTTPReceiveMessage,
    WebSocketReceiveMessage
]

ASGIReceiveCallable: TypeAlias = Callable[[], Awaitable[ASGIReceiveEvent]]

HTTPSendMessage: TypeAlias = Union[
    HTTPResponseStartEvent,
    HTTPResponseBodyEvent,
    HTTPResponseTrailersEvent,
    HTTPServerPushEvent,
    HTTPDisconnectEvent
]

WebSocketSendMessage: TypeAlias = Union[
    WebSocketAcceptEvent,
    WebSocketSendEvent,
    WebSocketResponseStartEvent,
    WebSocketResponseBodyEvent,
    WebSocketCloseEvent
]

LifeSpanSendMessage: TypeAlias = Union[
    LifespanStartupCompleteEvent,
    LifespanStartupFailedEvent,
    LifespanShutdownCompleteEvent,
    LifespanShutdownFailedEvent
]

ASGISendEvent: TypeAlias = Union[
    HTTPSendMessage,
    WebSocketSendMessage
]

ASGISendCallable: TypeAlias = Callable[[ASGISendEvent], Awaitable[None]]
