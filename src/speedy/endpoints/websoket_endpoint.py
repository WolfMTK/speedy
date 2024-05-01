import json
from typing import Any

from speedy.enums import WebSocketEncoding
from speedy.exceptions import RuntimeWebSocketException
from speedy.protocols import BaseWebSocketEndpoint
from speedy.status_code import WS_1003_UNSUPPORTED_DATA
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable, Message
from speedy.websocket import WebSocket


class WebSocketEndpoint(BaseWebSocketEndpoint):
    def __init__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable,
            send: ASGISendCallable
    ) -> None:
        assert scope['type'] == 'websocket'
        self.scope = scope
        self.receive = receive
        self.send = send
        self._encoding: str | WebSocketEncoding | None = None

    @property
    def encoding(self) -> str | WebSocketEncoding | None:
        return self._encoding

    @encoding.setter
    def encoding(self, value: str | WebSocketEncoding | None) -> None:
        self._encoding = value

    async def dispatch(self) -> None:
        ...

    async def decode(
            self,
            websocket: WebSocket,
            message: Message,
            json_library: str = 'json'
    ) -> Any:
        """
        Decode a message sent over a websocket.

        Supported libraries for decoding to json: `json`, `ujson`, `orjson`.
        """
        match self._encoding:
            case WebSocketEncoding.TEXT:
                return await self._decode_text(websocket, message)
            case WebSocketEncoding.BYTES:
                return await self._decode_bytes(websocket, message)
            case WebSocketEncoding.JSON:
                return await self._decode_json(websocket, message, json_library)

        if message.get(WebSocketEncoding.TEXT):
            return message[WebSocketEncoding.TEXT]
        return message[WebSocketEncoding.BYTES]

    async def on_connect(self) -> None:
        ...

    async def on_receive(self) -> None:
        ...

    async def on_disconnect(self) -> None:
        ...

    async def _decode_text(self, websocket: WebSocket, message: Message) -> Any:
        if WebSocketEncoding.TEXT not in message:
            await websocket.close(code=WS_1003_UNSUPPORTED_DATA)
            raise RuntimeWebSocketException('Expected text websocket messages')
        return message[WebSocketEncoding.TEXT]

    async def _decode_bytes(self, websocket: WebSocket, message: Message) -> Any:
        if WebSocketEncoding.BYTES not in message:
            await websocket.close(code=WS_1003_UNSUPPORTED_DATA)
            raise RuntimeWebSocketException('Expected bytes websocket messages')

    async def _decode_json(self, websocket: WebSocket, message: Message, json_library: str) -> Any:
        if (text := message.get(WebSocketEncoding.BYTES)) is not None:
            text = text.decode('utf-8')
        else:
            text = message[WebSocketEncoding.TEXT]

        if json_library == 'ujson':
            import ujson

            try:
                return ujson.loads(text)  # type: ignore
            except ujson.JSONDecodeError:
                exception_flag = True
        elif json_library == 'orjson':
            import orjson

            try:
                return orjson.loads(text)  # type: ignore
            except orjson.JSONDecodeError:
                exception_flag = True
        else:
            try:
                return json.loads(text)  # type: ignore
            except json.decoder.JSONDecodeError:
                exception_flag = True

        if exception_flag:
            await websocket.close(code=WS_1003_UNSUPPORTED_DATA)
            raise RuntimeWebSocketException('Malformed JSON data received')
