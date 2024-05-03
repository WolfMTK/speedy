import json
from typing import Any

from speedy.enums import WebSocketEncoding
from speedy.exceptions import RuntimeWebSocketException
from speedy.protocols import AbstractWebSocket
from speedy.protocols import BaseWebSocketEndpoint
from speedy.status_code import WS_1003_UNSUPPORTED_DATA
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable, Message


class WebSocketEndpoint(BaseWebSocketEndpoint):
    encoding: str | None = None
    json_library: str = 'json'

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

    async def dispatch(self) -> None:
        ...

    async def decode(
            self,
            websocket: AbstractWebSocket,
            message: Message,
    ) -> Any:
        """
        Decode a message sent over a websocket.

        Supported libraries for decoding to json: `json`, `ujson`, `orjson`.
        """
        match self.encoding:
            case WebSocketEncoding.TEXT:
                return await self._decode_text(websocket, message)
            case WebSocketEncoding.BYTES:
                return await self._decode_bytes(websocket, message)
            case WebSocketEncoding.JSON:
                return await self._decode_json(websocket, message)

        if message.get(WebSocketEncoding.TEXT):
            return message[WebSocketEncoding.TEXT]  # type: ignore[typeddict-item]
        return message[WebSocketEncoding.BYTES]  # type: ignore[typeddict-item]

    async def on_connect(self, websocket: AbstractWebSocket) -> None:
        """
        Override to handle an incoming websocket connection.

        Accepts the connection when the websocket is open:
        ```
            await websocket.accept()
        ```
        """

    async def on_receive(self, websocket: AbstractWebSocket, data: Any) -> None:
        """
        Override to handle an incoming websocket message.

        Send bytes:
        ```
            await websocket.send_bytes(data)
        ```
        Send text:
        ```
            await websocket.send_text(data)
        ```
        Send json:
        ```
            await websocket.send_json(data, mode='text', json_library='json')
        ```
            mode takes as arguments: 'text' or 'bytes'
            json_library takes as arguments: 'json', 'ujson', 'orjson'
        """

    async def on_disconnect(self, websocket: AbstractWebSocket, code: int) -> None:
        """
        Override to handle a disconnecting websocket.

        Closing the connection:
        ```
            await websocket.close(code=code)
        ```
        """

    async def _decode_text(self, websocket: AbstractWebSocket, message: Message) -> Any:
        if WebSocketEncoding.TEXT not in message:
            await websocket.close(code=WS_1003_UNSUPPORTED_DATA)
            raise RuntimeWebSocketException('Expected text websocket messages')
        return message[WebSocketEncoding.TEXT]  # type: ignore[typeddict-item]

    async def _decode_bytes(self, websocket: AbstractWebSocket, message: Message) -> Any:
        if WebSocketEncoding.BYTES not in message:
            await websocket.close(code=WS_1003_UNSUPPORTED_DATA)
            raise RuntimeWebSocketException('Expected bytes websocket messages')

    async def _decode_json(self, websocket: AbstractWebSocket, message: Message) -> Any:
        if self.json_library not in ('json', 'ujson', 'orjson'):
            self.json_library = 'json'

        if (
                text := message.get(WebSocketEncoding.BYTES)  # type: ignore[unused-ignore]
        ) is not None:
            text = text.decode('utf-8')  # type: ignore[attr-defined]
        else:
            text = message[WebSocketEncoding.TEXT]  # type: ignore[typeddict-item]

        if self.json_library == 'ujson':
            import ujson
            try:
                return ujson.loads(text)  # type: ignore[arg-type]
            except ujson.JSONDecodeError:
                exception_flag = True
        elif self.json_library == 'orjson':
            import orjson
            try:
                return orjson.loads(text)  # type: ignore[arg-type]
            except orjson.JSONDecodeError:
                exception_flag = True
        else:
            try:
                return json.loads(text)  # type: ignore[arg-type]
            except json.decoder.JSONDecodeError:
                exception_flag = True

        if exception_flag:
            await websocket.close(code=WS_1003_UNSUPPORTED_DATA)
            raise RuntimeWebSocketException('Malformed JSON data received')
