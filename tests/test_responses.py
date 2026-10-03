import datetime as dt
import sys
import time
from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from dataclasses import dataclass
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

import anyio
import pytest


from speedy import status
from speedy.background import BackgroundTask
from speedy.datastructures import Headers
from speedy.requests import ClientDisconnect, Request
from speedy.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from speedy.testclient import TestClient
from speedy.types import Message, Receive, Scope, Send
from tests.types import TestClientFactory


class TestBasicResponses:
    @pytest.mark.parametrize(
        ("content", "media_type"),
        [("hello, world", "text/plain"), (b"xxxxx", "image/png")],
        ids=("str", "bytes"),
    )
    def test_content(self, test_client_factory: TestClientFactory, content: Any, media_type: str) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            response = Response(content, media_type=media_type)
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.content == (content if isinstance(content, bytes) else content.encode())

    def test_json_none_response(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            response = JSONResponse(None)
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.json() is None
        assert response.content == b"null"

    def test_response_phrase(self, test_client_factory: TestClientFactory) -> None:
        app = Response(status_code=204)
        client = test_client_factory(app)
        response = client.get("/")
        assert response.reason_phrase == "No Content"

        app = Response(b"", status_code=123)
        client = test_client_factory(app)
        response = client.get("/")
        assert response.reason_phrase == ""

    def test_response_memoryview(self, test_client_factory: TestClientFactory) -> None:
        app = Response(content=memoryview(b"\xc0"))
        client: TestClient = test_client_factory(app)
        response = client.get("/")
        assert response.content == b"\xc0"

    def test_response_headers(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            headers = {"x-header-1": "123", "x-header-2": "456"}
            response = Response("hello, world", media_type="text/plain", headers=headers)
            response.headers["x-header-2"] = "789"
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.headers["x-header-1"] == "123"
        assert response.headers["x-header-2"] == "789"


class TestRedirectResponses:
    @pytest.mark.parametrize(
        ("redirect_path", "expected_url"),
        [
            ("/", "http://testserver/"),
            ("/I ♥ Starlette/", "http://testserver/I%20%E2%99%A5%20Starlette/"),
        ],
        ids=("plain", "quoted"),
    )
    def test_redirect(self, test_client_factory: TestClientFactory, redirect_path: str, expected_url: str) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            if scope["path"] == redirect_path:
                response = Response("hello, world", media_type="text/plain")
            else:
                response = RedirectResponse(redirect_path)
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/redirect")
        assert response.text == "hello, world"
        assert response.url == expected_url

    def test_redirect_response_content_length_header(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            if scope["path"] == "/":
                response = Response("hello", media_type="text/plain")
            else:
                response = RedirectResponse("/")
            await response(scope, receive, send)

        client: TestClient = test_client_factory(app)
        response = client.request("GET", "/redirect", follow_redirects=False)
        assert response.url == "http://testserver/redirect"
        assert response.headers["content-length"] == "0"


def _make_custom_async_iterator() -> Any:
    class CustomAsyncIterator:
        def __init__(self) -> None:
            self._called = 0

        def __aiter__(self) -> AsyncIterator[str]:
            return self

        async def __anext__(self) -> str:
            if self._called == 5:
                raise StopAsyncIteration()
            self._called += 1
            return str(self._called)

    return CustomAsyncIterator()


class _CustomAsyncIterable:
    async def __aiter__(self) -> AsyncIterator[str | bytes]:
        for i in range(5):
            yield str(i + 1)


class TestStreamingResponses:
    def test_streaming_response(self, test_client_factory: TestClientFactory) -> None:
        filled_by_bg_task = ""

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            async def numbers(minimum: int, maximum: int) -> AsyncIterator[str]:
                for i in range(minimum, maximum + 1):
                    yield str(i)
                    if i != maximum:
                        yield ", "
                    await anyio.sleep(0)

            async def numbers_for_cleanup(start: int = 1, stop: int = 5) -> None:
                nonlocal filled_by_bg_task
                async for thing in numbers(start, stop):
                    filled_by_bg_task = filled_by_bg_task + thing

            cleanup_task = BackgroundTask(numbers_for_cleanup, start=6, stop=9)
            generator = numbers(1, 5)
            response = StreamingResponse(generator, media_type="text/plain", background=cleanup_task)
            await response(scope, receive, send)

        assert filled_by_bg_task == ""
        client = test_client_factory(app)
        response = client.get("/")
        assert response.text == "1, 2, 3, 4, 5"
        assert filled_by_bg_task == "6, 7, 8, 9"

    @pytest.mark.parametrize(
        "stream_factory",
        [pytest.param(_make_custom_async_iterator, id="iterator"), pytest.param(_CustomAsyncIterable, id="iterable")],
    )
    def test_custom_stream_source(self, test_client_factory: TestClientFactory, stream_factory: Any) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            response = StreamingResponse(stream_factory(), media_type="text/plain")
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.text == "12345"

    def test_sync_streaming_response(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            def numbers(minimum: int, maximum: int) -> Iterator[str]:
                for i in range(minimum, maximum + 1):
                    yield str(i)
                    if i != maximum:
                        yield ", "

            generator = numbers(1, 5)
            response = StreamingResponse(generator, media_type="text/plain")
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.text == "1, 2, 3, 4, 5"

    @pytest.mark.parametrize(
        ("headers", "expected_length"),
        [({}, None), ({"content-length": "10"}, "10")],
        ids=("unknown", "known"),
    )
    def test_content_length(
            self, test_client_factory: TestClientFactory, headers: dict[str, str], expected_length: str | None
    ) -> None:
        app = StreamingResponse(content=iter(["hello", "world"]), headers=headers)
        client: TestClient = test_client_factory(app)
        response = client.get("/")
        if expected_length is None:
            assert "content-length" not in response.headers
        else:
            assert response.headers["content-length"] == expected_length

    def test_streaming_response_memoryview(self, test_client_factory: TestClientFactory) -> None:
        app = StreamingResponse(content=iter([memoryview(b"\xc0"), memoryview(b"\xf5")]))
        client: TestClient = test_client_factory(app)
        response = client.get("/")
        assert response.content == b"\xc0\xf5"

    @pytest.mark.anyio
    async def test_streaming_response_stops_if_receiving_http_disconnect(self) -> None:
        streamed = 0

        disconnected = anyio.Event()

        async def receive_disconnect() -> Message:
            await disconnected.wait()
            return {"type": "http.disconnect"}

        async def send(message: Message) -> None:
            nonlocal streamed
            if message["type"] == "http.response.body":
                streamed += len(message.get("body", b""))
                if streamed >= 16:
                    disconnected.set()

        async def stream_indefinitely() -> AsyncIterator[bytes]:
            while True:
                await anyio.sleep(0)
                yield b"chunk "

        response = StreamingResponse(content=stream_indefinitely())

        with anyio.move_on_after(1) as cancel_scope:
            await response({"type": "http"}, receive_disconnect, send)
        assert not cancel_scope.cancel_called, "Content streaming should stop itself."

    @pytest.mark.anyio
    async def test_streaming_response_on_client_disconnects(self) -> None:
        chunks = bytearray()
        streamed = False

        async def receive_disconnect() -> Message:
            raise NotImplementedError

        async def send(message: Message) -> None:
            nonlocal streamed
            if message["type"] == "http.response.body":
                if not streamed:
                    chunks.extend(message.get("body", b""))
                    streamed = True
                else:
                    raise OSError

        async def stream_indefinitely() -> AsyncGenerator[bytes, None]:
            while True:
                await anyio.sleep(0)
                yield b"chunk"

        stream = stream_indefinitely()
        response = StreamingResponse(content=stream)

        with anyio.move_on_after(1) as cancel_scope:
            with pytest.raises(ClientDisconnect):
                await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive_disconnect, send)
        assert not cancel_scope.cancel_called, "Content streaming should stop itself."
        assert chunks == b"chunk"
        await stream.aclose()

    @pytest.mark.anyio
    async def test_streaming_response_runs_background_on_websocket_scope(self) -> None:
        background_called = False
        sent: list[Message] = []

        async def receive() -> Message:
            return {}

        async def send(message: Message) -> None:
            sent.append(message)

        def run_background() -> None:
            nonlocal background_called
            background_called = True

        async def stream() -> AsyncIterator[bytes]:
            yield b"chunk"

        response = StreamingResponse(stream(), background=BackgroundTask(run_background))

        await response({"type": "websocket"}, receive, send)

        assert background_called
        assert [message["type"] for message in sent] == [
            "websocket.http.response.start",
            "websocket.http.response.body",
            "websocket.http.response.body",
        ]


class TestFileResponses:
    def test_file_response(self, tmp_path: Path, test_client_factory: TestClientFactory) -> None:
        path = tmp_path / "xyz"
        content = b"<file content>" * 1000
        path.write_bytes(content)

        filled_by_bg_task = ""

        async def numbers(minimum: int, maximum: int) -> AsyncIterator[str]:
            for i in range(minimum, maximum + 1):
                yield str(i)
                if i != maximum:
                    yield ", "
                await anyio.sleep(0)

        async def numbers_for_cleanup(start: int = 1, stop: int = 5) -> None:
            nonlocal filled_by_bg_task
            async for thing in numbers(start, stop):
                filled_by_bg_task = filled_by_bg_task + thing

        cleanup_task = BackgroundTask(numbers_for_cleanup, start=6, stop=9)

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            response = FileResponse(path=path, filename="example.png", background=cleanup_task)
            await response(scope, receive, send)

        assert filled_by_bg_task == ""
        client = test_client_factory(app)
        response = client.get("/")
        expected_disposition = 'attachment; filename="example.png"'
        assert response.status_code == status.HTTP_200_OK
        assert response.content == content
        assert response.headers["content-type"] == "image/png"
        assert response.headers["content-disposition"] == expected_disposition
        assert "content-length" in response.headers
        assert "last-modified" in response.headers
        assert "etag" in response.headers
        assert filled_by_bg_task == "6, 7, 8, 9"

    def test_file_response_known_size(self, tmp_path: Path, test_client_factory: TestClientFactory) -> None:
        path = tmp_path / "xyz"
        content = b"<file content>" * 1000
        path.write_bytes(content)

        app = FileResponse(path=path, filename="example.png")
        client: TestClient = test_client_factory(app)
        response = client.get("/")
        assert response.headers["content-length"] == str(len(content))

    @pytest.mark.anyio
    async def test_file_response_on_head_method(self, tmp_path: Path) -> None:
        path = tmp_path / "xyz"
        content = b"<file content>" * 1000
        path.write_bytes(content)

        app = FileResponse(path=path, filename="example.png")

        async def receive() -> Message:
            ...

        async def send(message: Message) -> None:
            if message["type"] == "http.response.start":
                assert message["status"] == status.HTTP_200_OK
                headers = Headers(raw=message["headers"])
                assert headers["content-type"] == "image/png"
                assert "content-length" in headers
                assert "content-disposition" in headers
                assert "last-modified" in headers
                assert "etag" in headers
            elif message["type"] == "http.response.body":
                assert message["body"] == b""
                assert message["more_body"] is False

        await app({"type": "http", "method": "head", "headers": [(b"key", b"value")]}, receive, send)

    @pytest.mark.parametrize(
        ("filename", "media_type", "expected_content_type"),
        [
            pytest.param("example.png", "image/jpeg", "image/jpeg", id="explicit"),
            pytest.param("file.unknownext", None, "application/octet-stream", id="fallback"),
        ],
    )
    def test_media_type(
            self,
            tmp_path: Path,
            test_client_factory: TestClientFactory,
            filename: str,
            media_type: str | None,
            expected_content_type: str,
    ) -> None:
        path = tmp_path / filename
        path.write_bytes(b"<file content>")

        kwargs: dict[str, Any] = {} if media_type is None else {"media_type": media_type}
        app = FileResponse(path=path, filename=filename, **kwargs)
        client: TestClient = test_client_factory(app)
        response = client.get("/")
        assert response.headers["content-type"] == expected_content_type

    @pytest.mark.parametrize(
        ("path_factory", "match"),
        [
            pytest.param(lambda tmp_path: tmp_path, "is not a file", id="directory"),
            pytest.param(lambda tmp_path: tmp_path / "404.txt", "does not exist", id="missing"),
        ],
    )
    def test_file_response_error(
            self,
            tmp_path: Path,
            test_client_factory: TestClientFactory,
            path_factory: Any,
            match: str,
    ) -> None:
        app = FileResponse(path=path_factory(tmp_path), filename="example.png")
        client = test_client_factory(app)
        with pytest.raises(RuntimeError) as exc_info:
            client.get("/")
        assert match in str(exc_info.value)

    def test_file_response_with_chinese_filename(self, tmp_path: Path, test_client_factory: TestClientFactory) -> None:
        content = b"file content"
        filename = "你好.txt"
        path = tmp_path / filename
        path.write_bytes(content)
        app = FileResponse(path=path, filename=filename)
        client = test_client_factory(app)
        response = client.get("/")
        expected_disposition = "attachment; filename*=utf-8''%E4%BD%A0%E5%A5%BD.txt"
        assert response.status_code == status.HTTP_200_OK
        assert response.content == content
        assert response.headers["content-disposition"] == expected_disposition

    def test_file_response_with_inline_disposition(
            self, tmp_path: Path, test_client_factory: TestClientFactory
    ) -> None:
        content = b"file content"
        filename = "hello.txt"
        path = tmp_path / filename
        path.write_bytes(content)
        app = FileResponse(path=path, filename=filename, content_disposition_type="inline")
        client = test_client_factory(app)
        response = client.get("/")
        expected_disposition = 'inline; filename="hello.txt"'
        assert response.status_code == status.HTTP_200_OK
        assert response.content == content
        assert response.headers["content-disposition"] == expected_disposition

    def test_file_response_with_range_header(self, tmp_path: Path, test_client_factory: TestClientFactory) -> None:
        content = b"file content"
        filename = "hello.txt"
        path = tmp_path / filename
        path.write_bytes(content)
        etag = '"a_non_autogenerated_etag"'
        app = FileResponse(path=path, filename=filename, headers={"etag": etag})
        client = test_client_factory(app)
        response = client.get("/", headers={"range": "bytes=0-4", "if-range": etag})
        assert response.status_code == status.HTTP_206_PARTIAL_CONTENT
        assert response.content == content[:5]
        assert response.headers["etag"] == etag
        assert response.headers["content-length"] == "5"
        assert response.headers["content-range"] == f"bytes 0-4/{len(content)}"

    @pytest.mark.anyio
    async def test_file_response_with_pathsend(self, tmp_path: Path) -> None:
        path = tmp_path / "xyz"
        content = b"<file content>" * 1000
        path.write_bytes(content)

        app = FileResponse(path=path, filename="example.png")

        async def receive() -> Message:
            ...

        async def send(message: Message) -> None:
            if message["type"] == "http.response.start":
                assert message["status"] == status.HTTP_200_OK
                headers = Headers(raw=message["headers"])
                assert headers["content-type"] == "image/png"
                assert "content-length" in headers
                assert "content-disposition" in headers
                assert "last-modified" in headers
                assert "etag" in headers
            elif message["type"] == "http.response.pathsend":
                assert message["path"] == str(path)

        await app(
            {"type": "http", "method": "get", "headers": [], "extensions": {"http.response.pathsend": {}}},
            receive,
            send,
        )


class TestCookies:
    def test_set_cookie(self, test_client_factory: TestClientFactory, monkeypatch: pytest.MonkeyPatch) -> None:
        mocked_now = dt.datetime(2037, 1, 22, 12, 0, 0, tzinfo=dt.timezone.utc)
        monkeypatch.setattr(time, "time", lambda: mocked_now.timestamp())

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            response = Response("Hello, world!", media_type="text/plain")
            response.set_cookie(
                "mycookie",
                "myvalue",
                max_age=10,
                expires=10,
                path="/",
                domain="localhost",
                secure=True,
                httponly=True,
                samesite="none",
                partitioned=True if sys.version_info >= (3, 14) else False,
            )
            await response(scope, receive, send)

        partitioned_text = "Partitioned; " if sys.version_info >= (3, 14) else ""

        client = test_client_factory(app)
        response = client.get("/")
        assert response.text == "Hello, world!"
        assert (
                response.headers["set-cookie"] == "mycookie=myvalue; Domain=localhost; expires=Thu, 22 Jan 2037 12:00:10 GMT; "
                                                  f"HttpOnly; Max-Age=10; {partitioned_text}Path=/; SameSite=none; Secure"
        )

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="Only relevant for <3.14")
    def test_set_cookie_raises_for_invalid_python_version(
            self,
            test_client_factory: TestClientFactory,
    ) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            response = Response("Hello, world!", media_type="text/plain")
            with pytest.raises(ValueError):
                response.set_cookie("mycookie", "myvalue", partitioned=True)
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.text == "Hello, world!"
        assert response.headers.get("set-cookie") is None

    @pytest.mark.parametrize(
        ("set_cookie_kwargs", "expected_header"),
        [
            pytest.param({"path": None}, "mycookie=myvalue; SameSite=lax", id="path"),
            pytest.param({"samesite": None}, "mycookie=myvalue; Path=/", id="samesite"),
        ],
    )
    def test_set_cookie_omitted_field(
            self,
            test_client_factory: TestClientFactory,
            set_cookie_kwargs: dict[str, Any],
            expected_header: str,
    ) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            response = Response("Hello, world!", media_type="text/plain")
            response.set_cookie("mycookie", "myvalue", **set_cookie_kwargs)
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.text == "Hello, world!"
        assert response.headers["set-cookie"] == expected_header

    @pytest.mark.parametrize(
        "expires",
        [
            pytest.param(dt.datetime(2037, 1, 22, 12, 0, 10, tzinfo=dt.timezone.utc), id="datetime"),
            pytest.param("Thu, 22 Jan 2037 12:00:10 GMT", id="str"),
            pytest.param(10, id="int"),
        ],
    )
    def test_expires_on_set_cookie(
            self,
            test_client_factory: TestClientFactory,
            monkeypatch: pytest.MonkeyPatch,
            expires: str,
    ) -> None:
        mocked_now = dt.datetime(2037, 1, 22, 12, 0, 0, tzinfo=dt.timezone.utc)
        monkeypatch.setattr(time, "time", lambda: mocked_now.timestamp())

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            response = Response("Hello, world!", media_type="text/plain")
            response.set_cookie("mycookie", "myvalue", expires=expires)
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        cookie = SimpleCookie(response.headers.get("set-cookie"))
        assert cookie["mycookie"]["expires"] == "Thu, 22 Jan 2037 12:00:10 GMT"

    def test_delete_cookie(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            response = Response("Hello, world!", media_type="text/plain")
            if request.cookies.get("mycookie"):
                response.delete_cookie("mycookie")
            else:
                response.set_cookie("mycookie", "myvalue")
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.cookies["mycookie"]
        response = client.get("/")
        assert not response.cookies.get("mycookie")

    @pytest.mark.parametrize("partitioned", [False, True])
    def test_delete_cookie_partitioned(self, partitioned: bool) -> None:
        response = Response()
        if partitioned and sys.version_info < (3, 14):
            with pytest.raises(ValueError, match="Partitioned cookies are only supported in Python 3.14 and above"):
                response.delete_cookie("mycookie", secure=True, samesite="none", partitioned=partitioned)
            assert "set-cookie" not in response.headers
            return

        response.delete_cookie("mycookie", secure=True, samesite="none", partitioned=partitioned)

        header = response.headers["set-cookie"]
        assert ("Partitioned" in header) is partitioned
        cookie = SimpleCookie(header)["mycookie"]
        assert cookie["max-age"] == "0"
        assert cookie["secure"] is True


class TestHeaderPopulation:
    def test_populate_headers(self, test_client_factory: TestClientFactory) -> None:
        app = Response(content="hi", headers={}, media_type="text/html")
        client = test_client_factory(app)
        response = client.get("/")
        assert response.text == "hi"
        assert response.headers["content-length"] == "2"
        assert response.headers["content-type"] == "text/html; charset=utf-8"

    def test_head_method(self, test_client_factory: TestClientFactory) -> None:
        app = Response("hello, world", media_type="text/plain")
        client = test_client_factory(app)
        response = client.head("/")
        assert response.text == ""

    @pytest.mark.parametrize(
        ("status_code", "expected_content_length"),
        [(200, "0"), (204, None)],
        ids=("default", "status_204"),
    )
    def test_empty_response_content_length(
            self, test_client_factory: TestClientFactory, status_code: int, expected_content_length: str | None
    ) -> None:
        app = Response(status_code=status_code)
        client: TestClient = test_client_factory(app)
        response = client.get("/")
        assert response.headers.get("content-length") == expected_content_length
        assert response.content == b""
        assert "content-type" not in response.headers

    def test_non_empty_response(self, test_client_factory: TestClientFactory) -> None:
        app = Response(content="hi")
        client: TestClient = test_client_factory(app)
        response = client.get("/")
        assert response.headers["content-length"] == "2"

    def test_response_do_not_add_redundant_charset(self, test_client_factory: TestClientFactory) -> None:
        app = Response(media_type="text/plain; charset=utf-8")
        client = test_client_factory(app)
        response = client.get("/")
        assert response.headers["content-type"] == "text/plain; charset=utf-8"


README = """\
# BáiZé

Powerful and exquisite WSGI/ASGI framework/toolkit.

The minimize implementation of methods required in the Web framework. No redundant implementation means that you can freely customize functions without considering the conflict with baize's own implementation.

Under the ASGI/WSGI protocol, the interface of the request object and the response object is almost the same, only need to add or delete `await` in the appropriate place. In addition, it should be noted that ASGI supports WebSocket but WSGI does not.
"""


@pytest.fixture
def readme_file(tmp_path: Path) -> Path:
    filepath = tmp_path / "README.txt"
    filepath.write_bytes(README.encode("utf8"))
    return filepath


@pytest.fixture
def file_response_client(readme_file: Path, test_client_factory: TestClientFactory) -> TestClient:
    return test_client_factory(app=FileResponse(str(readme_file)))


@dataclass
class MultipartPart:
    headers: dict[bytes, bytes]
    data: bytes


def parse_multipart_data(data: bytes, boundary: bytes | str) -> list[MultipartPart]:
    if isinstance(boundary, str):
        boundary = boundary.encode()

    chunks = data.split(b"--" + boundary)
    assert chunks[0] == b"", "unexpected preamble"
    assert chunks[-1] == b"--", "missing closing boundary"

    parts: list[MultipartPart] = []
    for chunk in chunks[1:-1]:
        assert chunk.startswith(b"\r\n") and chunk.endswith(b"\r\n"), "malformed part"
        raw_headers, _, body = chunk[2:-2].partition(b"\r\n\r\n")
        headers: dict[bytes, bytes] = {}
        for line in raw_headers.split(b"\r\n"):
            name, _, value = line.partition(b": ")
            headers[name] = value
        parts.append(MultipartPart(headers, body))
    return parts


class TestFileResponseRanges:
    @pytest.mark.parametrize("method", ["get", "head"])
    def test_without_range(self, file_response_client: TestClient, method: str) -> None:
        response = getattr(file_response_client, method)("/")
        assert response.status_code == 200
        assert "content-range" not in response.headers
        assert response.headers["content-length"] == str(len(README.encode("utf8")))
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        if method == "get":
            assert response.text == README
        else:
            assert response.content == b""

    @pytest.mark.parametrize("method", ["get", "head"])
    def test_range(self, file_response_client: TestClient, method: str) -> None:
        response = getattr(file_response_client, method)("/", headers={"Range": "bytes=0-100"})
        assert response.status_code == 206
        assert response.headers["content-range"] == f"bytes 0-100/{len(README.encode('utf8'))}"
        assert response.headers["content-length"] == "101"
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        if method == "get":
            assert response.content == README.encode("utf8")[:101]
        else:
            assert response.content == b""

    def test_range_if_range(self, file_response_client: TestClient) -> None:
        response = file_response_client.head("/", headers={"Range": "bytes=200-300"})
        assert response.status_code == 206
        etag = response.headers["etag"]

        response = file_response_client.head(
            "/",
            headers={"Range": "bytes=200-300", "if-range": etag[:-1]},
        )
        assert response.status_code == 200

        response = file_response_client.head(
            "/",
            headers={"Range": "bytes=200-300", "if-range": etag},
        )
        assert response.status_code == 206

    @pytest.mark.parametrize("method", ["get", "head"])
    def test_range_multi(self, file_response_client: TestClient, method: str) -> None:
        response = getattr(file_response_client, method)("/", headers={"Range": "bytes=0-100, 200-300"})
        assert response.status_code == 206
        assert "content-range" not in response.headers
        assert response.headers["content-length"] == "448"
        assert response.headers["content-type"].startswith("multipart/byteranges; boundary=")
        if method == "head":
            assert response.content == b""

    @pytest.mark.parametrize(
        ("stop", "expected_status"),
        [(200, 206), (202, 200)],
        ids=("within_limit", "exceeded"),
    )
    def test_range_count_limit(self, file_response_client: TestClient, stop: int, expected_status: int) -> None:
        ranges = ",".join(f"{index}-{index}" for index in range(0, stop, 2))
        response = file_response_client.get("/", headers={"Range": f"bytes={ranges}"})

        assert response.status_code == expected_status
        if expected_status == 206:
            assert response.headers["content-type"].startswith("multipart/byteranges; boundary=")
        else:
            assert "content-range" not in response.headers
            assert response.text == README

    @pytest.mark.parametrize(
        ("range_header", "expected_text"),
        [
            pytest.param("bytes: 0-1000", None, id="malformed"),
            pytest.param("items=0-100", "Only support bytes range", id="wrong_units"),
            pytest.param("bytes=", "Range header: range must be requested", id="empty"),
            pytest.param("bytes=100-0", "Range header: start must be less than end", id="inverted"),
            pytest.param("bytes=5-4", "Range header: start must be less than end", id="inverted_single_byte"),
        ],
    )
    def test_range_invalid(
            self, file_response_client: TestClient, range_header: str, expected_text: str | None
    ) -> None:
        response = file_response_client.get("/", headers={"Range": range_header})
        assert response.status_code == 400
        if expected_text is not None:
            assert response.text == expected_text

    @pytest.mark.parametrize(
        "range_header",
        ["bytes=100, 0-50", "bytes= - , 0-50", "bytes=abc-def, 0-50"],
        ids=("no_dash", "empty_start_end", "non_numeric"),
    )
    def test_range_fallback_to_valid_part(self, file_response_client: TestClient, range_header: str) -> None:
        response = file_response_client.get("/", headers={"Range": range_header})
        assert response.status_code == 206
        assert response.headers["content-range"] == f"bytes 0-50/{len(README.encode('utf8'))}"

    @pytest.mark.parametrize(
        ("suffix", "expected_content"),
        [(100, README.encode("utf8")[-100:]), (1000, README.encode("utf8"))],
        ids=("partial", "larger_than_file"),
    )
    def test_suffix_range(self, file_response_client: TestClient, suffix: int, expected_content: bytes) -> None:
        file_size = len(README.encode("utf8"))
        response = file_response_client.get("/", headers={"Range": f"bytes=-{suffix}"})
        assert response.status_code == 206
        assert response.headers["content-range"] == f"bytes {max(file_size - suffix, 0)}-{file_size - 1}/{file_size}"
        assert response.headers["content-length"] == str(min(suffix, file_size))
        assert response.content == expected_content

    def test_range_head_max(self, file_response_client: TestClient) -> None:
        response = file_response_client.head("/", headers={"Range": f"bytes=0-{len(README.encode('utf8')) + 1}"})
        assert response.status_code == 206

    def test_range_416(self, file_response_client: TestClient) -> None:
        response = file_response_client.head("/", headers={"Range": f"bytes={len(README.encode('utf8')) + 1}-"})
        assert response.status_code == 416
        assert response.headers["Content-Range"] == f"bytes */{len(README.encode('utf8'))}"

    def test_single_byte_range(self, file_response_client: TestClient) -> None:
        response = file_response_client.get("/", headers={"Range": "bytes=5-5"})
        assert response.status_code == 206
        assert response.headers["content-range"] == f"bytes 5-5/{len(README.encode('utf8'))}"
        assert response.headers["content-length"] == "1"

    def test_merge_ranges(self, file_response_client: TestClient) -> None:
        response = file_response_client.get("/", headers={"Range": "bytes=0-100, 50-200"})
        assert response.status_code == 206
        assert response.headers["content-length"] == "201"
        assert response.headers["content-range"] == f"bytes 0-200/{len(README.encode('utf8'))}"

    def test_multiple_calls(self, file_response_client: TestClient) -> None:
        response = file_response_client.get("/", headers={"Range": "bytes=0-100"})
        assert response.status_code == 206

        response = file_response_client.get("/")
        assert response.status_code == 200
        assert "content-range" not in response.headers
        assert response.headers["content-length"] == str(len(README.encode("utf8")))
        assert response.headers["content-type"] == "text/plain; charset=utf-8"

    def test_insert_ranges(self, file_response_client: TestClient) -> None:
        response = file_response_client.get("/", headers={"Range": "bytes=100-200, 0-50"})

        assert response.status_code == 206
        assert "content-range" not in response.headers
        assert response.headers["content-type"].startswith("multipart/byteranges; boundary=")
        boundary = response.headers["content-type"].split("boundary=")[1]
        assert response.text.splitlines() == [
            f"--{boundary}",
            "Content-Type: text/plain; charset=utf-8",
            "Content-Range: bytes 0-50/526",
            "",
            "# BáiZé",
            "",
            "Powerful and exquisite WSGI/ASGI framewo",
            f"--{boundary}",
            "Content-Type: text/plain; charset=utf-8",
            "Content-Range: bytes 100-200/526",
            "",
            "ds required in the Web framework. No redundant implementation means that you can freely customize fun",
            f"--{boundary}--",
        ]

        parts = parse_multipart_data(response._content, boundary)
        assert all(
            value == b"text/plain; charset=utf-8"
            for part in parts
            for key, value in part.headers.items()
            if key == b"Content-Type"
        )
        assert len(parts) == 2
        assert parts[0].headers[b"Content-Range"] == b"bytes 0-50/526"
        assert parts[0].data == "# BáiZé\n\nPowerful and exquisite WSGI/ASGI framewo".encode()
        assert parts[1].headers[b"Content-Range"] == b"bytes 100-200/526"
        assert (
                parts[1].data
                == b"ds required in the Web framework. No redundant implementation means that you can freely customize fun"
        )

    @pytest.mark.anyio
    async def test_multi_small_chunk_size(self, readme_file: Path) -> None:
        class SmallChunkSizeFileResponse(FileResponse):
            chunk_size = 10

        app = SmallChunkSizeFileResponse(path=str(readme_file))

        received_chunks: list[bytes] = []
        start_message: dict[str, Any] = {}

        async def receive() -> Message:
            raise NotImplementedError("Should not be called!")

        async def send(message: Message) -> None:
            if message["type"] == "http.response.start":
                start_message.update(message)
            elif message["type"] == "http.response.body":
                received_chunks.append(message["body"])

        await app({"type": "http", "method": "get", "headers": [(b"range", b"bytes=0-15,20-35,35-50")]}, receive, send)
        assert start_message["status"] == 206

        headers = Headers(raw=start_message["headers"])
        assert "content-range" not in headers
        assert headers.get("accept-ranges") == "bytes"
        assert "content-length" in headers
        assert "last-modified" in headers
        assert "etag" in headers
        assert headers["content-type"].startswith("multipart/byteranges; boundary=")
        boundary = headers["content-type"].split("boundary=")[1]

        assert received_chunks == [
            f"--{boundary}\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Range: bytes 0-15/526\r\n\r\n".encode(),
            b"# B\xc3\xa1iZ\xc3\xa9\n",
            b"\nPower",
            b"\r\n",
            f"--{boundary}\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Range: bytes 20-50/526\r\n\r\n".encode(),
            b"and exquis",
            b"ite WSGI/A",
            b"SGI framew",
            b"o",
            b"\r\n",
            f"--{boundary}--".encode(),
        ]
