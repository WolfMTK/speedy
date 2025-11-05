import asyncio
from collections.abc import Mapping
from typing import Generator, Any
from unittest.mock import Mock

import pytest
from httpx import Request

from speedy.status_code import HTTP_500_INTERNAL_SERVER_ERROR
from speedy.testing.transport import TestClientTransport, ConnectionUpgradeExceptionError, SyncTestClientTransport


def make_request(
        method: str = "GET",
        url: str = "http://testserver/",
        headers: Mapping[str, str] | None = None,
        content: Any = b"",
) -> Request:
    return Request(method=method, url=url, headers=headers or {}, content=content)


def _make_client(app):
    client = Mock()
    client.app = app

    def mock_call(func, *args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    client.blocking_portal = Mock()
    client.blocking_portal.call = mock_call
    return client


async def test_handle_async_request_success() -> None:
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"OK", "more_body": False})

    client = Mock(app=app)
    transport = TestClientTransport(client=client, raise_server_exceptions=True)
    response = await transport.handle_async_request(make_request())
    await response.aread()

    assert response.status_code == 200
    assert response.content == b"OK"
    assert response.headers["content-type"] == "text/plain"


async def test_handle_async_request_with_template() -> None:
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.template", "template": "test.html", "context": {"user": "foo"}})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    client = Mock(app=app)
    transport = TestClientTransport(client=client, raise_server_exceptions=True)
    response = await transport.handle_async_request(make_request())
    await response.aread()

    assert response.status_code == 200
    assert response.template == "test.html"  # noqa
    assert response.context == {"user": "foo"}  # noqa


async def test_head_request_no_body() -> None:
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ignored", "more_body": False})

    client = Mock(app=app)
    transport = TestClientTransport(client=client, raise_server_exceptions=True)
    response = await transport.handle_async_request(make_request(method="HEAD"))
    await response.aread()

    assert response.status_code == 200
    assert response.content == b""


async def test_request_with_generator_body() -> None:
    def body_gen() -> Generator[bytes, None, None]:
        yield b"chunk1"
        yield b"chunk2"

    gen = body_gen()

    class FakeRequest:
        def read(self): return gen

    client = Mock()
    transport = TestClientTransport(client=client, raise_server_exceptions=True)

    response_complete = Mock()
    response_complete.is_set = Mock(return_value=True)
    context = {
        "request_complete": False,
        "response_complete": response_complete,
        "raw_kwargs": {},
        "response_started": False,
        "template": None,
        "context": None,
    }
    receive = transport.create_receive(FakeRequest(), context)

    assert await receive() == {"type": "http.request", "body": b"chunk1", "more_body": True}
    assert await receive() == {"type": "http.request", "body": b"chunk2", "more_body": True}
    assert await receive() == {"type": "http.request", "body": b"", "more_body": False}
    assert await receive() == {"type": "http.disconnect"}


async def test_raise_server_exceptions_false_catches_exception() -> None:
    async def app(scope, receive, send):
        raise ValueError("boom")

    client = Mock(app=app)
    transport = TestClientTransport(client=client, raise_server_exceptions=False)
    response = await transport.handle_async_request(make_request())
    await response.aread()

    assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR
    assert response.content == b""


async def test_raise_server_exceptions_true_propagates_exception() -> None:
    async def app(scope, receive, send):
        raise RuntimeError("boom")

    client = Mock(app=app)
    transport = TestClientTransport(client=client, raise_server_exceptions=True)

    with pytest.raises(RuntimeError, match="boom"):
        await transport.handle_async_request(make_request())


async def test_websocket_raises_connection_upgrade() -> None:
    client = Mock()
    transport = TestClientTransport(client=client, raise_server_exceptions=True)
    request = make_request(url="ws://testserver/ws")

    with pytest.raises(ConnectionUpgradeExceptionError) as exc:
        await transport.handle_async_request(request)

    scope = exc.value.scope
    assert scope["type"] == "websocket"
    assert scope["path"] == "/ws"


async def test_no_response_started_500_if_no_raise() -> None:
    async def app(scope, receive, send): ...

    client = Mock(app=app)
    transport = TestClientTransport(client=client, raise_server_exceptions=False)
    response = await transport.handle_async_request(make_request())
    await response.aread()

    assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR


async def test_no_response_started_assertion_if_raise() -> None:
    async def app(scope, receive, send): ...

    client = Mock(app=app)
    transport = TestClientTransport(client=client, raise_server_exceptions=True)

    with pytest.raises(AssertionError, match="TestClient did not receive any response"):
        await transport.handle_async_request(make_request())


async def test_parse_request_preserves_raw_path_and_query() -> None:
    client = Mock()
    transport = TestClientTransport(client=client, raise_server_exceptions=True)
    request = make_request(url="http://testserver/foo%20bar?x=1%262")
    scope = transport.parse_request(request)

    assert scope["path"] == "/foo bar"
    assert scope["raw_path"] == b"/foo%20bar"
    assert scope["query_string"] == b"x=1%262"


async def test_host_header_handling() -> None:
    client = Mock()
    transport = TestClientTransport(client=client, raise_server_exceptions=True)
    request = make_request(
        url="http://custom:8080/path",
        headers={"host": "custom.example.com:9000"},
    )
    scope = transport.parse_request(request)

    headers = {k.decode(): v.decode() for k, v in scope["headers"]}
    assert headers["host"] == "custom.example.com:9000"
    assert scope["server"] == ("custom", 8080)


def test_sync_transport_success() -> None:
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"sync ok", "more_body": False})

    client = _make_client(app)
    transport = SyncTestClientTransport(client=client, raise_server_exceptions=True)
    response = transport.handle_request(make_request())
    response.read()

    assert response.status_code == 200
    assert response.content == b"sync ok"


def test_sync_transport_exception_propagated() -> None:
    async def failing_app(scope, receive, send):
        raise RuntimeError("propagated error")

    client = _make_client(failing_app)
    transport = SyncTestClientTransport(client=client, raise_server_exceptions=True)
    request = make_request()

    with pytest.raises(RuntimeError, match="propagated error"):
        transport.handle_request(request)


def test_sync_transport_exception_suppressed() -> None:
    async def failing_app(scope, receive, send):
        raise ValueError("suppressed")

    client = _make_client(failing_app)
    transport = SyncTestClientTransport(client=client, raise_server_exceptions=False)
    response = transport.handle_request(make_request())
    response.read()

    assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR
    assert response.content == b""
