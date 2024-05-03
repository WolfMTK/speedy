import json
from collections.abc import Iterable
from typing import cast, Any

from speedy.datastructures import (
    WebSocketCloseEvent,
    WebSocketAcceptEvent,
    WebSocketSendTextEvent,
    WebSocketSendBytesEvent,
)
from speedy.enums import ScopeType, WebSocketState, WebSocketStatusEvent, WebSocketEncoding
from speedy.exceptions import RuntimeWebSocketException, WebSocketDisconnect
from speedy.protocols import HTTPConnection, AbstractWebSocket
from speedy.status_code import WS_1000_NORMAL_CLOSURE, WS_1006_ABNORMAL_CLOSURE
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable, Message


class WebSocket(AbstractWebSocket, HTTPConnection):
    def __init__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable,
            send: ASGISendCallable
    ) -> None:
        assert scope['type'] == ScopeType.WEBSOCKET

        self._scope = scope
        self._receive = receive
        self._send = send
        self._client_state = WebSocketState.CONNECTING
        self._application_state = WebSocketState.CONNECTING

    @property
    def client_state(self) -> str:
        return self._client_state

    @property
    def application_state(self) -> str:
        return self._application_state

    async def send(self, message: Message) -> None:
        """ Send ASGI websocket messages, ensuring valid state transitions. """
        match self.application_state:
            case WebSocketState.CONNECTING:
                await self._send_is_connecting(message)
            case WebSocketState.CONNECTED:
                await self._send_is_connected(message)
            case WebSocketState.RESPONSE:
                await self._send_is_response(message)
            case _:
                raise RuntimeWebSocketException(
                    'Cannot call "send" once a close message has been send.'
                )

    async def send_text(self, data: str) -> None:
        """ Send text in a websocket messages. """
        await self.send(vars(WebSocketSendTextEvent(text=data)))  # type: ignore[arg-type]

    async def send_bytes(self, data: bytes) -> None:
        """ Send bytes in a websocket messages. """
        await self.send(vars(WebSocketSendBytesEvent(bytes=data)))  # type: ignore[arg-type]

    async def send_json(self, data: Any, mode: str = 'text', json_library: str = 'json') -> None:
        """ Send json in a websocket messages.

        mode: text | bytes
        json_library: json, ujson, orjson
        """
        if mode not in (WebSocketEncoding.TEXT, WebSocketEncoding.BYTES):
            raise RuntimeWebSocketException('The "mode" argument should be "text" or "binary".')

        if json_library not in ('json', 'ujson', 'orjson'):
            raise RuntimeWebSocketException(
                'The "json_library" argument should be "json", "ujson" or "orjson"'
            )
        text = self._send_json(data, json_library)
        if mode == WebSocketEncoding.TEXT:
            await self.send_text(text)
        else:
            await self.send_bytes(text.encode('utf-8'))

    async def receive(self) -> Message:
        """ Receive ASGI websocket messages, ensuring valid state transitions. """
        match WebSocketState:
            case WebSocketState.CONNECTING:
                return await self._receive_is_connecting()
            case WebSocketState.CONNECTED:
                return await self._receive_is_connected()
            case _:
                raise RuntimeWebSocketException(
                    'Cannot call "receive" once a disconnect message has been received.'
                )

    async def receive_text(self) -> str:
        """ Receive text from a websocket messages. """
        if self.application_state != WebSocketState.CONNECTED:
            raise RuntimeWebSocketException(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await self.receive()
        self._raise_on_disconnect(message)
        return cast(str, message['WebSocketEncoding.TEXT'])  # type: ignore[typeddict-item]

    async def receive_bytes(self) -> bytes:
        """ Receive bytes from a websocket messages. """
        if self.application_state != WebSocketState.CONNECTED:
            raise RuntimeWebSocketException(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await self.receive()
        self._raise_on_disconnect(message)
        return cast(bytes, message[WebSocketEncoding.BYTES])  # type: ignore[typeddict-item]

    async def receive_json(
            self,
            mode: str = WebSocketEncoding.TEXT,
            json_library: str = 'json'
    ) -> Any:
        """
        Receive json from a websocket messages.

        mode: text or binary
        json_library: json, ujson or orjson
        """
        if mode not in (WebSocketEncoding.TEXT, WebSocketEncoding.BYTES):
            raise RuntimeWebSocketException('The "mode" argument should be "text" or "binary"')

        if json_library not in ('json', 'ujson', 'orjson'):
            raise RuntimeWebSocketException(
                'The "json_library" argument should be "json", "ujson" or "orjson"'
            )

        if self.application_state != WebSocketState.CONNECTED:
            raise RuntimeWebSocketException(
                'WebSocket is not connected. Need to call "accept" first.'
            )
        message = await self.receive()
        self._raise_on_disconnect(message)

        if (
                text := message.get(WebSocketEncoding.BYTES)
        ) is not None:
            text = text.decode('utf-8')  # type: ignore[attr-defined]
        else:
            text = message[WebSocketEncoding.TEXT]  # type: ignore[typeddict-item]
        return self._receive_json(cast(str, text), json_library)

    async def accept(
            self,
            subprotocol: str | None = None,
            headers: Iterable[tuple[bytes, bytes]] | None = None
    ) -> None:
        """ Accept a connection when websocket is opened. """
        if self.client_state == WebSocketState.CONNECTING:
            # Waiting for connection
            await self.receive()
        await self._send(
            vars(self._accept_websocket(subprotocol, headers))  # type: ignore[arg-type]
        )

    async def close(
            self,
            code: int = WS_1000_NORMAL_CLOSURE,
            reason: str | None = None
    ) -> None:
        """ Close the connection. """
        await self._send(vars(self._close_websocket(code, reason)))  # type: ignore[arg-type]

    async def _send_is_connecting(self, message: Message) -> None:
        type_message = message['type']
        if type_message not in (
                WebSocketStatusEvent.ACCEPT,
                WebSocketStatusEvent.CLOSE,
                WebSocketStatusEvent.START
        ):
            raise RuntimeWebSocketException(
                'Expected ASGI message "websocket.accept", '
                f'"websocket.close" or "websocket.http.response.start", but got {type_message}'
            )
        match type_message:
            case WebSocketStatusEvent.CLOSE:
                self._application_state = WebSocketState.DISCONNECTED
            case WebSocketStatusEvent.START:
                self._application_state = WebSocketState.RESPONSE
            case _:
                self._application_state = WebSocketState.CONNECTED
        await self._send(message)  # type: ignore[arg-type]

    async def _send_is_connected(self, message: Message) -> None:
        type_message = message['type']
        if type_message not in (WebSocketStatusEvent.SEND,
                                WebSocketStatusEvent.CLOSE):
            raise RuntimeWebSocketException(
                'Expected ASGI message "websocket.send" or "websocket.close", '
                f'but got {type_message}'
            )
        if type_message == WebSocketStatusEvent.CLOSE:
            self._application_state = WebSocketState.DISCONNECTED
        try:
            await self._send(message)  # type: ignore[arg-type]
        except OSError:
            self._application_state = WebSocketState.DISCONNECTED
            raise WebSocketDisconnect(code=WS_1006_ABNORMAL_CLOSURE)

    async def _send_is_response(self, message: Message) -> None:
        type_message = message['type']
        if type_message != WebSocketStatusEvent.BODY:
            raise RuntimeWebSocketException(
                'Expected ASGI message "websocket.http.response.body", '
                f'but got {type_message}'
            )
        if not message.get('more_body', False):
            self._application_state = WebSocketState.DISCONNECTED
        await self._send(message)

    async def _receive_is_connecting(self) -> Message:
        message = await self._receive()
        type_message = message['type']
        if type_message != WebSocketStatusEvent.CONNECT:
            raise RuntimeWebSocketException(
                f'Expected ASGI message "websocket.connect", but got {type_message}'
            )
        self._client_state = WebSocketState.CONNECTED
        return cast(Message, message)

    async def _receive_is_connected(self) -> Message:
        message = await self._receive()
        type_message = message['type']
        if type_message not in (WebSocketStatusEvent.RECEIVE,
                                WebSocketStatusEvent.DISCONNECT):
            raise RuntimeWebSocketException(
                'Expected ASGI message "websocket.receive" or "websocket.disconnect", '
                f'but got {type_message}'
            )

        if type_message == WebSocketStatusEvent.DISCONNECT:
            self._client_state = WebSocketState.DISCONNECTED
        return cast(Message, message)

    def _raise_on_disconnect(self, message: Message) -> None:
        if message['type'] == WebSocketStatusEvent.DISCONNECT:
            raise WebSocketDisconnect(
                cast(int, message['code']),
                cast(str | None, message.get('reason'))
            )

    def _close_websocket(
            self,
            code: int,
            reason: str | None
    ) -> WebSocketCloseEvent:
        if reason is None:
            return WebSocketCloseEvent(code=code)
        return WebSocketCloseEvent(code=code, reason=reason)

    def _accept_websocket(
            self,
            subprotocol: str | None = None,
            headers: Iterable[tuple[bytes, bytes]] | None = None
    ) -> WebSocketAcceptEvent:
        if headers is None:
            return WebSocketAcceptEvent(subprotocol=subprotocol, headers=[])
        return WebSocketAcceptEvent(subprotocol=subprotocol, headers=headers)

    def _receive_json(self, text: str, library: str) -> Any:
        if library == 'ujson':
            import ujson
            return ujson.loads(text)
        elif library == 'orjson':
            import orjson
            return orjson.loads(text)
        return json.loads(text)

    def _send_json(self, data: Any, json_library: str) -> str:
        if json_library == 'ujson':
            import ujson
            return ujson.dumps(data, separators=(',', ':'), ensure_ascii=False)
        if json_library == 'orjson':
            import orjson
            return orjson.dumps(data).decode('utf-8')
        return json.dumps(data, separators=(',', ':'), ensure_ascii=False)
