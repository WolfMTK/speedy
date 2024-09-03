import json
from collections.abc import AsyncGenerator
from typing import Generic, Any

from speedy import RequestEncodingType
from speedy._multipart import parse_content_header, MultiPartFormParser
from speedy._parsers import parse_url_encoded_form_data
from speedy.connection.base import ASGIConnection, empty_receive, empty_send
from speedy.datastructures import FormMultiDict
from speedy.exceptions import RequestException, InternalServerException
from speedy.protocols.connection import UserT, AuthT, StateT
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable, Method

SERVER_PUSH_HEADERS = {
    'accept',
    'accept-encoding',
    'accept-language',
    'cache-control',
    'user-agent',
}


class Request(Generic[UserT, AuthT, StateT], ASGIConnection[UserT, AuthT, StateT]):
    """ The application Request class. """

    def __init__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable = empty_receive,
            send: ASGISendCallable = empty_send
    ) -> None:
        if scope['type'] != 'http':
            raise RequestException('Invalid scope type. The type `http` was expected.')
        super().__init__(scope, receive, send)
        self._body: bytes | None = None
        self._is_connected: bool = True
        self._json: Any = None
        self._form: FormMultiDict | None = None
        self._content_type: tuple[str, dict[str, str]] | None = None

    @property
    def method(self) -> Method:
        """ Return the request method. """
        return self.scope['method']

    @property
    def content_type(self) -> tuple[str, dict[str, str],]:
        """ Return the request content type. """
        if self._content_type is None:
            self._content_type = parse_content_header(self.headers.get('Content-Type', ''))
        return self._content_type

    async def stream(self) -> AsyncGenerator[bytes, None]:
        """ Return an async generator that streams chunks of bytes. """
        if self._body is not None:
            yield self._body
            yield b''
            return

        if not self._is_connected:
            raise InternalServerException('stream consumed')

        while message := await self.receive():
            if message['type'] == 'http.request':
                body = message.get('body', b'')
                if not message.get('more_body', False):
                    break
                if body:
                    yield body
            elif message['type'] == 'http.disconnect':
                raise InternalServerException('client disconnected prematurely')
        self._is_connected = False
        yield b''

    async def body(self) -> bytes:
        """ Return the body of the request. """
        if self._body is None:
            self._body = b''.join([chunk async for chunk in self.stream()])
        return self._body

    async def json(self) -> Any:
        """ Retrieve the json request body from the request """
        if self._json is None:
            body = await self.body()
            self._json = json.loads(body)
        return self._json

    async def form(self, multipart_limit: int = 1000) -> FormMultiDict:
        """ Retrieve form data from the request. """
        if self._form is None:
            content_type, options = self.content_type
            if content_type == RequestEncodingType.MULTI_PART:
                form_data = MultiPartFormParser(
                    body=await self.body(),
                    boundary=options.get('boundary', '').encode(),
                    multipart_limit=multipart_limit
                ).parser()
            elif content_type == RequestEncodingType.URL_ENCODED:
                form_data = parse_url_encoded_form_data(
                    await self.body()
                )
            else:
                form_data = {}

            items = []
            for key, value in form_data.items():
                if isinstance(value, list):
                    items.extend((key, v) for v in value)
                else:
                    items.append((key, value))
            self._form = FormMultiDict(items)

        return self._form

    async def send_push_promise(self, path: str) -> None:
        """ Send a push promise. """
        if 'http.response.push' in self.scope.get('extensions', {}):
            raw_headers = [
                (header_name.encode('latin-1'), value.encode('latin-1'))
                for header_name in SERVER_PUSH_HEADERS
                for value in self.headers.getlist(header_name)
            ]
            await self.send(
                {
                    'type': 'http.response.push',
                    'path': path,
                    'headers': raw_headers
                }
            )
