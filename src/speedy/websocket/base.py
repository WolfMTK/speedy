from speedy.datastructures import CloseWebSocket
from speedy.enums import ScopeType
from speedy.protocols.request import HTTPConnection
from speedy.status_code import WS_1000_NORMAL_CLOSURE
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable


class WebSocket(HTTPConnection):
    def __init__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        assert scope['type'] == ScopeType.WEBSOCKET
        self.scope = scope
        self.receive = receive
        self.send = send

    async def close(self, code: int = WS_1000_NORMAL_CLOSURE, reason: str | None = None) -> None:
        """ Close the connection. """
        await self.send(vars(self._close_websocket(code, reason)))

    def _close_websocket(self, code: int, reason: str | None) -> CloseWebSocket:
        if reason is None:
            return CloseWebSocket(code=code)
        return CloseWebSocket(code=code, reason=reason)
