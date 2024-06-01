from typing import AsyncGenerator

from speedy.exceptions import InternalServerException
from speedy.protocols.request import AbstractRequest
from speedy.types import Scope, ASGISendCallable, ASGIReceiveCallable, Method, HttpScope, HTTPReceiveMessage
from .base import ASGIConnect, empty_send, empty_receive


class Request(AbstractRequest, ASGIConnect):
    """ The Speedy Request class. """

    scope: HttpScope
    receive: HTTPReceiveMessage

    def __init__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable = empty_receive,
            send: ASGISendCallable = empty_send  # type: ignore[assignment]
    ) -> None:
        super().__init__(scope, receive, send)
        assert scope['type'] == 'http'
        self.is_connected: bool = True
        self.is_disconnect: bool = False

    @property
    def method(self) -> Method:
        """ Return the request method. """
        return self.scope['method']

    async def stream(self) -> AsyncGenerator[bytes, None]:
        """ Return an async generator that streams chunks of bytes. """
        if hasattr(self, '_body'):
            yield self._body
            yield b''
            return

        if not self.is_connected:
            raise InternalServerException('Stream consumed')

        while self.is_connected:
            event = self.receive
            if event['type'] == 'http.request':

                if event['body']:
                    yield event['body']

                if not event.get('more_body', False):
                    self.is_connected = False

            elif event['type'] == 'http.disconnect':
                self.is_disconnect = True
                raise InternalServerException('client disconnected prematurely')

    async def body(self):
        """ Return the body of the request. """
        if not hasattr(self, '_body'):
            self._body = b''.join([val async for val in self.stream()])
        return self._body
