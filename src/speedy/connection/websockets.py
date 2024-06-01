from enum import Flag

from speedy.protocols.websockets import AbstractWebsocket
from .base import ASGIConnect, empty_send, empty_receive
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable, WebSocketScope, Message
from speedy.exceptions import WebSocketDisconnect

class WebSocketState(Flag):
    INIT = 0
    CONNECT = 1
    DISCONNECT = 2
    RECEIVE = 3

DISCONNECT_MESSAGE = "connection is disconnected"


class WebSocket(AbstractWebsocket, ASGIConnect):
    """ The Speedy WebSocket class. """

    scope: WebSocketScope

    def __init__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable = empty_receive,
            send: ASGISendCallable = empty_send
    ) -> None:
        super().__init__(scope, self.receive_wrapper(receive), send)
        self.connection_state = WebSocketState.INIT

    def receive_wrapper(self, receive: ASGIReceiveCallable) -> ASGIReceiveCallable:
        """ Wrapper for connection creation and event confirmation. """
        async def wrapped_receive() -> Message:
            if self.connection_state == WebSocketState.DISCONNECT:
                raise WebSocketDisconnect(DISCONNECT_MESSAGE)
            message = await receive()
            message_type = message['type']
            match message_type:
                case 'websocket.connect':
                    self.connection_state = WebSocketState.CONNECT
                case 'websocket.receive':
                    self.connection_state = WebSocketState.RECEIVE
                case _:
                    self.connection_state = WebSocketState.DISCONNECT
            return message
        return wrapped_receive
