from collections.abc import AsyncGenerator
from typing import Any, Self

import anyio

from speedy._speedy import MultiPartFormParser, parse_content_header, parse_json, parse_urlencoded_form
from speedy._speedy import Request as _Request
from speedy.concurrency import AwaitableOrContextManagerWrapper
from speedy.datastructures import FormMultiDict
from speedy.exceptions import ClientDisconnect
from speedy.types import HTTPScope, Message, Receive, ReceiveMessage, Send

__all__ = ["Request", "empty_receive", "empty_send"]

SERVER_PUSH_HEADERS_TO_COPY = {
    "accept",
    "accept-encoding",
    "accept-language",
    "cache-control",
    "user-agent",
}


async def empty_receive() -> ReceiveMessage:
    raise RuntimeError("Receive channel has not been made available")


async def empty_send(message: Message) -> None:
    raise RuntimeError("Send channel has not been made available")


class Request(_Request):
    """An HTTP request."""

    def __new__(cls, scope: HTTPScope, receive: Receive = empty_receive, send: Send = empty_send) -> Self:
        return super().__new__(cls, scope, receive, send)

    def __init__(self, scope: HTTPScope, receive: Receive, send: Send) -> None:
        self._stream_consumed = False
        self._is_disconnected = False
        self._form: FormMultiDict | None = None

    async def stream(self) -> AsyncGenerator[bytes, None]:
        """Yield the request body in chunks as it arrives."""
        if hasattr(self, "_body"):
            yield self._body
            yield b""
            return
        if self._stream_consumed:
            raise RuntimeError("Stream consumed")

        while not self._stream_consumed:
            message = await self.receive()
            match message["type"]:
                case "http.request":
                    self._stream_consumed = not message.get("more_body", False)
                    if chunk := message.get("body", b""):
                        yield chunk
                case "http.disconnect":
                    self._is_disconnected = True
                    raise ClientDisconnect()
                case _:
                    continue
        yield b""

    async def body(self) -> bytes:
        """Get the full request body."""
        if not hasattr(self, "_body"):
            self._body = b"".join([chunk async for chunk in self.stream()])
        return self._body

    async def json(self) -> Any:
        """Get the request body parsed as JSON."""
        if not hasattr(self, "_json"):
            self._json = parse_json(await self.body())
        return self._json

    def form(self, *, max_fields: int = 1000) -> AwaitableOrContextManagerWrapper:
        """Get the form body."""
        return AwaitableOrContextManagerWrapper(self._get_form(max_fields=max_fields))

    async def close(self) -> None:
        """Close any uploaded files in the parsed form."""
        if self._form is not None:
            await self._form.close()

    async def is_disconnected(self) -> bool:
        """Check whether the client has disconnected."""
        if self._is_disconnected:
            return True
        message: ReceiveMessage | dict[str, Any] = {}
        with anyio.CancelScope() as scope:
            scope.cancel()
            message = await self.receive()
        self._is_disconnected = message.get("type") == "http.disconnect"
        return self._is_disconnected

    async def send_push_promise(self, path: str) -> None:
        """Send an HTTP/2 server push promise, if supported."""
        if "http.response.push" not in self.scope.get("extensions", {}):
            return
        raw_headers = [
            (name.encode("latin-1"), value.encode("latin-1"))
            for name in SERVER_PUSH_HEADERS_TO_COPY
            for value in self.headers.getlist(name)
        ]
        await self._send({"type": "http.response.push", "path": path, "headers": raw_headers})

    async def _get_form(self, *, max_fields: int = 1000) -> FormMultiDict:
        if self._form is not None:
            return self._form

        content_type, params = parse_content_header(self.headers.get("content-type", ""))
        match content_type:
            case "multipart/form-data":
                boundary = params.get("boundary", "").encode("latin-1")
                parser = MultiPartFormParser(await self.body(), boundary, multipart_limit=max_fields)
                self._form = FormMultiDict(parser.parse_pairs())
            case "application/x-www-form-urlencoded":
                self._form = FormMultiDict(parse_urlencoded_form(await self.body()))
            case _:
                self._form = FormMultiDict()
        return self._form
