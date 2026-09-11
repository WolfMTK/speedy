import os
from collections.abc import AsyncIterable, Awaitable
from email.utils import formatdate
from mimetypes import guess_type
from secrets import token_hex
from typing import Any, Self
from urllib.parse import quote

import anyio

from speedy._speedy import (
    MalformedRangeHeader,
    RangeNotSatisfiable,
    compute_etag,
    dump_json,
    multipart_closing_boundary,
    multipart_content_length,
    multipart_range_header,
    parse_range_header,
)
from speedy._speedy import Response as _Response
from speedy.concurrency import create_collapsing_task_group, iterate_in_threadpool
from speedy.datastructures import URL, Headers, MutableHeaders
from speedy.exceptions import ClientDisconnect
from speedy.types import AsyncContentStream, ContentStream, Message, Receive, Scope, Send

__all__ = [
    "FileResponse",
    "HTMLResponse",
    "JSONResponse",
    "PlainTextResponse",
    "RedirectResponse",
    "Response",
    "StreamingResponse",
]


class Response(_Response):
    def _wrap_websocket_denial_send(self, send: Send) -> Send:
        async def wrapped(message: Message) -> None:
            message_type = message["type"]
            if message_type in {"http.response.start", "http.response.body"}:  # pragma: no branch
                message = {**message, "type": "websocket." + message_type}
            await send(message)

        return wrapped

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            send = self._wrap_websocket_denial_send(send)

        await send({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})
        await send({"type": "http.response.body", "body": self.body})

        if self.background is not None:
            await self.background()


class PlainTextResponse(Response):
    def __new__(
        cls,
        content: Any = None,
        status_code: int = 200,
        headers: Any = None,
        media_type: str | None = "text/plain",
        background: Any = None,
    ) -> Self:
        return super().__new__(cls, content, status_code, headers, media_type, background)


class HTMLResponse(Response):
    def __new__(
        cls,
        content: Any = None,
        status_code: int = 200,
        headers: Any = None,
        media_type: str | None = "text/html",
        background: Any = None,
    ) -> Self:
        return super().__new__(cls, content, status_code, headers, media_type, background)


class JSONResponse(Response):
    def __new__(
        cls,
        content: Any = None,
        status_code: int = 200,
        headers: Any = None,
        media_type: str | None = "application/json",
        background: Any = None,
    ) -> Self:
        body = dump_json(content)
        return super().__new__(cls, body, status_code, headers, media_type, background)


class RedirectResponse(Response):
    def __new__(
        cls,
        url: str | URL,
        status_code: int = 307,
        headers: Any = None,
        background: Any = None,
    ) -> Self:
        return super().__new__(cls, b"", status_code, headers, None, background)

    def __init__(
        self,
        url: str | URL,
        status_code: int = 307,
        headers: Any = None,
        background: Any = None,
    ) -> None:
        if not 300 <= status_code < 400:
            raise ValueError(f"Invalid redirect status code: {status_code} (must be 300-399)")
        self.headers["location"] = quote(str(url), safe=":/%#?=@[]!$&'()*+,;")


class StreamingResponse(Response):
    body_iterator: AsyncContentStream

    def __new__(
        cls,
        content: ContentStream,
        status_code: int = 200,
        headers: Any = None,
        media_type: str | None = None,
        background: Any = None,
    ) -> Self:
        return super().__new__(cls, b"", status_code, headers, media_type, background)

    def __init__(
        self,
        content: ContentStream,
        status_code: int = 200,
        headers: Any = None,
        media_type: str | None = None,
        background: Any = None,
    ) -> None:
        if "content-length" in self.headers:
            del self.headers["content-length"]
        self.body_iterator = content if isinstance(content, AsyncIterable) else iterate_in_threadpool(content)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            send = self._wrap_websocket_denial_send(send)
            await self.stream_response(send)
            if self.background is not None:
                await self.background()
            return

        spec_version = tuple(map(int, scope.get("asgi", {}).get("spec_version", "2.0").split(".")))
        if spec_version >= (2, 4):
            try:
                await self.stream_response(send)
            except OSError:
                raise ClientDisconnect() from None
        else:
            async with create_collapsing_task_group() as task_group:

                async def run_and_cancel(coro: Awaitable[None]) -> None:
                    await coro
                    task_group.cancel_scope.cancel()

                task_group.start_soon(run_and_cancel, self.stream_response(send))
                await run_and_cancel(self.listen_for_disconnect(receive))

        if self.background is not None:
            await self.background()

    async def listen_for_disconnect(self, receive: Receive) -> None:
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break

    async def stream_response(self, send: Send) -> None:
        await send({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})
        async for chunk in self.body_iterator:
            if not isinstance(chunk, bytes | memoryview):
                chunk = chunk.encode(self.charset)
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})


class FileResponse(Response):
    chunk_size = 64 * 1024
    max_ranges = 100

    def __new__(
        cls,
        path: str | os.PathLike[str],
        status_code: int = 200,
        headers: Any = None,
        media_type: str | None = None,
        background: Any = None,
        filename: str | None = None,
        stat_result: os.stat_result | None = None,
        content_disposition_type: str = "attachment",
    ) -> Self:
        resolved_media_type = media_type or guess_type(filename or str(path))[0] or "application/octet-stream"
        return super().__new__(cls, b"", status_code, headers, resolved_media_type, background)

    def __init__(
        self,
        path: str | os.PathLike[str],
        status_code: int = 200,
        headers: Any = None,
        media_type: str | None = None,
        background: Any = None,
        filename: str | None = None,
        stat_result: os.stat_result | None = None,
        content_disposition_type: str = "attachment",
    ) -> None:
        if "content-length" in self.headers:
            del self.headers["content-length"]

        self.path = path
        self.filename = filename
        self.headers.setdefault("accept-ranges", "bytes")

        if self.filename is not None:
            content_disposition_filename = quote(self.filename)
            if content_disposition_filename != self.filename:
                content_disposition = f"{content_disposition_type}; filename*=utf-8''{content_disposition_filename}"
            else:
                content_disposition = f'{content_disposition_type}; filename="{self.filename}"'
            self.headers.setdefault("content-disposition", content_disposition)

        self.stat_result = stat_result
        if stat_result is not None:
            self.set_stat_headers(stat_result)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        send_header_only = False
        send_pathsend = False
        if scope["type"] == "http":
            http_scope = scope
            send_header_only = http_scope["method"].upper() == "HEAD"
            send_pathsend = "http.response.pathsend" in http_scope.get("extensions", {})
        elif scope["type"] == "websocket":
            send = self._wrap_websocket_denial_send(send)

        if self.stat_result is None:
            try:
                stat_result = await anyio.to_thread.run_sync(os.stat, self.path)
                self.set_stat_headers(stat_result)
            except FileNotFoundError as exc:
                raise RuntimeError(f"File at path {self.path} does not exist.") from exc
            if not os.stat.S_ISREG(stat_result.st_mode):
                raise RuntimeError(f"File at path {self.path} is not a file.")
        else:
            stat_result = self.stat_result

        request_headers = Headers(scope=scope)
        http_range = request_headers.get("range")
        http_if_range = request_headers.get("if-range")

        if http_range is None or (http_if_range is not None and not self._should_use_range(http_if_range)):
            await self._handle_simple(send, send_header_only, send_pathsend)
        else:
            try:
                ranges = parse_range_header(http_range, stat_result.st_size, self.max_ranges)
            except MalformedRangeHeader as exc:
                return await PlainTextResponse(exc.content, status_code=400)(scope, receive, send)
            except RangeNotSatisfiable as exc:
                response = PlainTextResponse(status_code=416, headers={"content-range": f"bytes */{exc.max_size}"})
                return await response(scope, receive, send)

            match len(ranges):
                case 0:
                    await self._handle_simple(send, send_header_only, send_pathsend)
                case 1:
                    start, end = ranges[0]
                    await self._handle_single_range(send, start, end, stat_result.st_size, send_header_only)
                case _:
                    await self._handle_multiple_ranges(send, ranges, stat_result.st_size, send_header_only)

        if self.background is not None:
            await self.background()

    def set_stat_headers(self, stat_result: os.stat_result) -> None:
        self.headers.setdefault("content-length", str(stat_result.st_size))
        self.headers.setdefault("last-modified", formatdate(stat_result.st_mtime, usegmt=True))
        self.headers.setdefault("etag", compute_etag(stat_result.st_mtime, stat_result.st_size))

    def _should_use_range(self, http_if_range: str) -> bool:
        return http_if_range == self.headers["last-modified"] or http_if_range == self.headers["etag"]

    async def _handle_simple(self, send: Send, send_header_only: bool, send_pathsend: bool) -> None:
        await send({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})
        if send_header_only:
            await send({"type": "http.response.body", "body": b"", "more_body": False})
        elif send_pathsend:
            await send({"type": "http.response.pathsend", "path": str(self.path)})
        else:
            async with await anyio.open_file(self.path, mode="rb") as file:
                more_body = True
                while more_body:
                    chunk = await file.read(self.chunk_size)
                    more_body = len(chunk) == self.chunk_size
                    await send({"type": "http.response.body", "body": chunk, "more_body": more_body})

    async def _handle_single_range(
        self, send: Send, start: int, end: int, file_size: int, send_header_only: bool
    ) -> None:
        headers = MutableHeaders(raw=list(self.raw_headers))
        headers["content-range"] = f"bytes {start}-{end - 1}/{file_size}"
        headers["content-length"] = str(end - start)
        await send({"type": "http.response.start", "status": 206, "headers": headers.raw})
        if send_header_only:
            await send({"type": "http.response.body", "body": b"", "more_body": False})
        else:
            async with await anyio.open_file(self.path, mode="rb") as file:
                await file.seek(start)
                more_body = True
                while more_body:
                    chunk = await file.read(min(self.chunk_size, end - start))
                    start += len(chunk)
                    more_body = len(chunk) == self.chunk_size and start < end
                    await send({"type": "http.response.body", "body": chunk, "more_body": more_body})

    async def _handle_multiple_ranges(
        self,
        send: Send,
        ranges: list[tuple[int, int]],
        file_size: int,
        send_header_only: bool,
    ) -> None:
        boundary = token_hex(13)
        content_type = self.headers["content-type"]
        content_length = multipart_content_length(ranges, boundary, file_size, content_type)
        headers = MutableHeaders(raw=list(self.raw_headers))
        headers["content-type"] = f"multipart/byteranges; boundary={boundary}"
        headers["content-length"] = str(content_length)
        await send({"type": "http.response.start", "status": 206, "headers": headers.raw})
        if send_header_only:
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return

        async with await anyio.open_file(self.path, mode="rb") as file:
            for start, end in ranges:
                part_header = multipart_range_header(boundary, content_type, start, end, file_size)
                await send({"type": "http.response.body", "body": part_header, "more_body": True})
                await file.seek(start)
                while start < end:
                    chunk = await file.read(min(self.chunk_size, end - start))
                    start += len(chunk)
                    await send({"type": "http.response.body", "body": chunk, "more_body": True})
                await send({"type": "http.response.body", "body": b"\r\n", "more_body": True})
            await send({"type": "http.response.body", "body": multipart_closing_boundary(boundary), "more_body": False})
