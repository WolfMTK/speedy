import enum
from collections.abc import AsyncIterator, Iterable
from typing import Any, Self

from speedy._speedy import HTTPConnection, dump_json, parse_json
from speedy.exceptions import WebSocketDisconnect, WebSocketDisconnected
from speedy.responses import Response
from speedy.status import WS_1000_NORMAL_CLOSURE, WS_1006_ABNORMAL_CLOSURE
from speedy.types import Message, Receive, ReceiveMessage, Send, WebSocketScope


class WebSocketState(enum.Enum):
    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2
    RESPONSE = 3


class WebSocket(HTTPConnection):
    """A WebSocket connection."""

    def __new__(cls, scope: WebSocketScope, receive: Receive, send: Send) -> Self:
        return super().__new__(cls, scope)

    def __init__(self, scope: WebSocketScope, receive: Receive, send: Send) -> None:
        assert scope["type"] == "websocket"
        self._receive = receive
        self._send = send
        self.client_state = WebSocketState.CONNECTING
        self.application_state = WebSocketState.CONNECTING

    async def receive(self) -> ReceiveMessage:
        """Receive ASGI websocket messages, ensuring valid state transitions."""
        if self.client_state == WebSocketState.CONNECTING:
            message = await self._receive()
            message_type = message["type"]
            if message_type != "websocket.connect":
                raise RuntimeError(f'Expected ASGI message "websocket.connect", but got {message_type!r}')
            self.client_state = WebSocketState.CONNECTED
            return message
        elif self.client_state == WebSocketState.CONNECTED:
            message = await self._receive()
            message_type = message["type"]
            if message_type not in {"websocket.receive", "websocket.disconnect"}:
                raise RuntimeError(
                    f'Expected ASGI message "websocket.receive" or "websocket.disconnect", but got {message_type!r}'
                )
            if message_type == "websocket.disconnect":
                self.client_state = WebSocketState.DISCONNECTED
            return message
        else:
            raise WebSocketDisconnected('Cannot call "receive" once a disconnect message has been received.')

    async def send(self, message: Message) -> None:
        """Send ASGI websocket messages, ensuring valid state transitions."""
        if self.application_state == WebSocketState.CONNECTING:
            message_type = message["type"]
            if message_type not in {"websocket.accept", "websocket.close", "websocket.http.response.start"}:
                raise RuntimeError(
                    'Expected ASGI message "websocket.accept", "websocket.close" or "websocket.http.response.start", '
                    f"but got {message_type!r}"
                )
            if message_type == "websocket.close":
                self.application_state = WebSocketState.DISCONNECTED
            elif message_type == "websocket.http.response.start":
                self.application_state = WebSocketState.RESPONSE
            else:
                self.application_state = WebSocketState.CONNECTED
            await self._send(message)
        elif self.application_state == WebSocketState.CONNECTED:
            message_type = message["type"]
            if message_type not in {"websocket.send", "websocket.close"}:
                raise RuntimeError(
                    f'Expected ASGI message "websocket.send" or "websocket.close", but got {message_type!r}'
                )
            if message_type == "websocket.close":
                self.application_state = WebSocketState.DISCONNECTED
            try:
                await self._send(message)
            except OSError:
                self.application_state = WebSocketState.DISCONNECTED
                raise WebSocketDisconnect(code=WS_1006_ABNORMAL_CLOSURE) from None
        elif self.application_state == WebSocketState.RESPONSE:
            message_type = message["type"]
            if message_type != "websocket.http.response.body":
                raise RuntimeError(f'Expected ASGI message "websocket.http.response.body", but got {message_type!r}')
            if not message.get("more_body", False):
                self.application_state = WebSocketState.DISCONNECTED
            await self._send(message)
        else:
            raise WebSocketDisconnected('Cannot call "send" once a close message has been sent.')

    async def accept(
        self,
        subprotocol: str | None = None,
        headers: Iterable[tuple[bytes, bytes]] | None = None,
    ) -> None:
        """Accept the connection, waiting for the connect message first if needed."""
        if self.client_state == WebSocketState.CONNECTING:
            await self.receive()
        await self.send({"type": "websocket.accept", "subprotocol": subprotocol, "headers": list(headers or [])})

    async def receive_text(self) -> str:
        """Receive a text message."""
        if self.application_state != WebSocketState.CONNECTED:
            raise WebSocketDisconnected('WebSocket is not connected. Need to call "accept" first.')
        message = await self.receive()
        self._raise_on_disconnect(message)
        return message["text"]

    async def receive_bytes(self) -> bytes:
        """Receive a binary message."""
        if self.application_state != WebSocketState.CONNECTED:
            raise WebSocketDisconnected('WebSocket is not connected. Need to call "accept" first.')
        message = await self.receive()
        self._raise_on_disconnect(message)
        return message["bytes"]

    async def receive_json(self, mode: str = "text") -> Any:
        """Receive a message and parse it as JSON."""
        if mode not in {"text", "binary"}:
            raise RuntimeError('The "mode" argument should be "text" or "binary".')
        if self.application_state != WebSocketState.CONNECTED:
            raise WebSocketDisconnected('WebSocket is not connected. Need to call "accept" first.')
        message = await self.receive()
        self._raise_on_disconnect(message)
        receive_event = message
        raw = receive_event["bytes"] if mode == "binary" else receive_event["text"].encode("utf-8")
        return parse_json(raw)

    async def iter_text(self) -> AsyncIterator[str]:
        """Iterate over incoming text messages until disconnect."""
        try:
            while True:
                yield await self.receive_text()
        except WebSocketDisconnect:
            pass

    async def iter_bytes(self) -> AsyncIterator[bytes]:
        """Iterate over incoming binary messages until disconnect."""
        try:
            while True:
                yield await self.receive_bytes()
        except WebSocketDisconnect:
            pass

    async def iter_json(self) -> AsyncIterator[Any]:
        """Iterate over incoming messages, parsed as JSON, until disconnect."""
        try:
            while True:
                yield await self.receive_json()
        except WebSocketDisconnect:
            pass

    async def send_text(self, data: str) -> None:
        """Send a text message."""
        await self.send({"type": "websocket.send", "text": data, "bytes": None})

    async def send_bytes(self, data: bytes) -> None:
        """Send a binary message."""
        await self.send({"type": "websocket.send", "bytes": data, "text": None})

    async def send_json(self, data: Any, mode: str = "text") -> None:
        """Serialize data as JSON and send it."""
        if mode not in {"text", "binary"}:
            raise RuntimeError('The "mode" argument should be "text" or "binary".')
        body = dump_json(data)
        if mode == "text":
            await self.send({"type": "websocket.send", "text": body.decode("utf-8"), "bytes": None})
        else:
            await self.send({"type": "websocket.send", "bytes": body, "text": None})

    async def close(self, code: int = WS_1000_NORMAL_CLOSURE, reason: str | None = None) -> None:
        """Close the connection."""
        await self.send({"type": "websocket.close", "code": code, "reason": reason or ""})

    async def send_denial_response(self, response: Response) -> None:
        """Send response in place of accepting the connection (requires server support)."""
        if "websocket.http.response" in self.scope.get("extensions", {}):
            await response(self.scope, self._receive, self._send)
        else:
            raise RuntimeError("The server doesn't support the Websocket Denial Response extension.")

    def _raise_on_disconnect(self, message: ReceiveMessage) -> None:
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message["code"], message.get("reason"))


class WebSocketClose:
    def __init__(self, code: int = WS_1000_NORMAL_CLOSURE, reason: str | None = None) -> None:
        self.code = code
        self.reason = reason or ""

    async def __call__(self, scope: WebSocketScope, receive: Receive, send: Send) -> None:
        await send({"type": "websocket.close", "code": self.code, "reason": self.reason})
