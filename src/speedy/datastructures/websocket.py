from collections.abc import Iterable
from dataclasses import dataclass, field

from speedy.enums import WebSocketStatusEvent
from speedy.status_code import WS_1000_NORMAL_CLOSURE


@dataclass
class WebSocketCloseEvent:
    """ Datastructure ASGI `websocket.close` event. """

    type: str = WebSocketStatusEvent.CLOSE
    code: int = WS_1000_NORMAL_CLOSURE
    reason: str = ''


@dataclass
class WebSocketAcceptEvent:
    """ Datastructure ASGI `websocket.accept` event. """

    type: str = WebSocketStatusEvent.ACCEPT
    subprotocol: str | None = field(default=None)
    headers: Iterable[tuple[bytes, bytes]] | None = field(default=None)


@dataclass
class _WebSocketSendEvent:
    type: str = WebSocketStatusEvent.SEND_EVENT


@dataclass(kw_only=True)
class WebSocketSendTextEvent(_WebSocketSendEvent):
    """ Datastructure ASGI `websocket.send` event. """

    text: str


@dataclass(kw_only=True)
class WebSocketSendBytesEvent(_WebSocketSendEvent):
    """ Datastructure ASGI `websocket.send` event. """

    bytes: bytes
