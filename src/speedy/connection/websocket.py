import json
from collections.abc import AsyncIterator
from enum import Flag
from typing import Generic, Any, cast

from speedy.connection.base import ASGIConnection, empty_receive, empty_send
from speedy.datastructures import Headers
from speedy.exceptions import WebSocketException, WebSocketDisconnect
from speedy.protocols.connection import UserT, AuthT, StateT
from speedy.protocols.websocket import WebSocketMode
from speedy.types import (
    Scope,
    ASGIReceiveCallable,
    ASGISendCallable,
    ASGIReceiveEvent,
    ASGISendEvent,
    WebSocketSendEvent
)


class WebSocketState(Flag):
    INIT = 'INIT'
    CONNECT = 'CONNECT'
    RECEIVE = 'RECEIVE'
    DISCONNECT = 'DISCONNECT'


DISCONNECT_MESSAGE = 'connection is disconnected'


class WebSocket(Generic[UserT, AuthT, StateT], ASGIConnection[UserT, AuthT, StateT]):
    def __init__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable = empty_receive,
            send: ASGISendCallable = empty_send
    ) -> None:
        if scope['type'] != 'websocket':
            raise WebSocketException('Invalid scope type. The type `websocket` was expected.')
        super().__init__(scope, self.receive_wrapper(receive), self.send_wrapper(send))
        self.is_connect: WebSocketState = WebSocketState.INIT

    def receive_wrapper(self, receive: ASGIReceiveCallable) -> ASGIReceiveCallable:
        """ Wrap receive to set connection and validate events. """

        async def wrapped_receive() -> ASGIReceiveEvent:
            if self.is_connect == WebSocketState.DISCONNECT:
                raise WebSocketDisconnect(DISCONNECT_MESSAGE)
            message = await receive()
            if message['type'] == 'websocket.connect':
                self.is_connect = WebSocketState.CONNECT
            elif message['type'] == 'websocket.receive':
                self.is_connect = WebSocketState.RECEIVE
            else:
                self.is_connect = WebSocketState.DISCONNECT
            return message

        return wrapped_receive

    def send_wrapper(self, send: ASGISendCallable) -> ASGISendCallable:
        """ Wrap send to ensure that state is not disconnected. """

        async def wrapped_send(message: ASGISendEvent) -> None:
            if self.is_connect == WebSocketState.DISCONNECT:
                raise WebSocketDisconnect(DISCONNECT_MESSAGE)
            await send(message)

        return wrapped_send

    async def accept(
            self,
            subprotocol: str | None = None,
            headers: Headers | dict[str, Any] | list[tuple[bytes, bytes]] | None = None
    ) -> None:
        if self.is_connect == WebSocketState.INIT:
            await self.receive()

            _headers: list[tuple[bytes, bytes]] = []
            if isinstance(headers, list):
                _headers = headers
            elif isinstance(headers, dict):
                _headers = Headers(headers).raw
            elif isinstance(headers, Headers):
                _headers = Headers(headers).raw

            await self.send(
                {
                    'type': 'websocket.accept',
                    'subprotocol': subprotocol,
                    'headers': _headers
                }
            )

    async def receive_data(self, mode: WebSocketMode) -> str | bytes:
        """ Receive an event and returns the data stored on it. """
        if self.is_connect == WebSocketState.INIT:
            await self.accept()
        event = await self.receive()
        if event['type'] == 'websocket.disconnect':
            raise WebSocketDisconnect('disconnect event')

        if mode == 'text':
            return cast(str, event.get('text', ''))
        return cast(bytes, event.get('bytes', ''))

    async def receive_text(self) -> str:
        """ Receive data as text. """
        return await self.receive_data('text')

    async def receive_bytes(self) -> bytes:
        """ Receive data as bytes. """
        return await self.receive_data('bytes')

    async def receive_json(self, mode: WebSocketMode = 'text') -> Any:
        """ Receive data and decode it as json. """
        data = await self.receive_data(mode)

        if mode == 'bytes':
            data = data.decode('utf-8')
        return json.loads(data)

    async def iter_text(self) -> AsyncIterator[str]:
        """ Continuously receive data and yield it in str. """
        try:
            while True:
                yield await self.receive_text()
        except WebSocketDisconnect:
            pass

    async def iter_bytes(self) -> AsyncIterator[bytes]:
        """ Continuously receive data and yield it in bytes. """
        try:
            while True:
                yield await self.receive_bytes()
        except WebSocketDisconnect:
            pass

    async def iter_json(self, mode: WebSocketMode = 'text') -> AsyncIterator[Any]:
        """ Continuously receive data and yield it in json. """
        try:
            while True:
                yield await self.receive_json(mode)
        except WebSocketDisconnect:
            pass

    async def send_data(self, data: str | bytes, mode: WebSocketMode = 'text', encoding: str = 'utf-8') -> None:
        """ Send a websocket event. """
        if self.is_connect == WebSocketState.INIT:
            await self.accept()
        event: WebSocketSendEvent = {
            'type': 'websocket.send',
            'bytes': None,
            'text': None
        }
        if mode == 'binary':
            event['bytes'] = data if isinstance(data, bytes) else data.encode(encoding)
        else:
            event['text'] = data if isinstance(data, str) else data.decode(encoding)
        await self.send(event)

    async def send_text(self, data: bytes | str, encoding: str = 'utf-8') -> None:
        """ Send data in text key. """
        await self.send_data(data=data, encoding=encoding)

    async def send_bytes(self, data: bytes, encoding: str = 'utf-8') -> None:
        """ Send data in bytes key """
        await self.send_data(data=data, mode='bytes', encoding=encoding)

    async def send_json(self, data: Any, mode: WebSocketMode = 'text', encoding: str = 'utf-8') -> None:
        """ Send data as json. """
        text = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        await self.send_data(data=text, mode=mode, encoding=encoding)
