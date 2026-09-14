import sys
from pathlib import Path
from typing import Any, AsyncGenerator, MutableMapping

import anyio
import pytest
from anyio.abc import ObjectReceiveStream, ObjectSendStream
from speedy import status
from speedy.exceptions import WebSocketDisconnect, WebSocketDisconnected
from speedy.responses import FileResponse, Response, StreamingResponse
from speedy.testclient import WebSocketDenialResponse
from speedy.types import Message, Receive, Scope, Send
from speedy.websocket import WebSocket, WebSocketState
from tests.types import TestClientFactory


class TestWebSocketBasics:
    def test_websocket_url(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            await websocket.send_json({"url": str(websocket.url)})
            await websocket.close()

        client = test_client_factory(app)
        with client.websocket_connect("/123?a=abc") as websocket:
            data = websocket.receive_json()
            assert data == {"url": "ws://testserver/123?a=abc"}

    def test_websocket_port(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            await websocket.send_json({"port": websocket.url.port})
            await websocket.close()

        client = test_client_factory(app)
        with client.websocket_connect("ws://example.com:123/123?a=abc") as websocket:
            data = websocket.receive_json()
            assert data == {"port": 123}

    def test_websocket_query_params(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            query_params = dict(websocket.query_params)
            await websocket.accept()
            await websocket.send_json({"params": query_params})
            await websocket.close()

        client = test_client_factory(app)
        with client.websocket_connect("/?a=abc&b=456") as websocket:
            data = websocket.receive_json()
            assert data == {"params": {"a": "abc", "b": "456"}}

    @pytest.mark.skipif(
        any(module in sys.modules for module in ("brotli", "brotlicffi")),
        reason='urllib3 includes "br" to the "accept-encoding" headers.',
    )
    def test_websocket_headers(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            headers = dict(websocket.headers)
            await websocket.accept()
            await websocket.send_json({"headers": headers})
            await websocket.close()

        client = test_client_factory(app)
        with client.websocket_connect("/") as websocket:

            probe_request = client.build_request("GET", "/")
            accept_encoding = probe_request.headers["accept-encoding"]
            expected_headers = {
                "accept": "*/*",
                "accept-encoding": accept_encoding,
                "connection": "upgrade",
                "host": "testserver",
                "user-agent": "testclient",
                "sec-websocket-key": "testserver==",
                "sec-websocket-version": "13",
            }
            data = websocket.receive_json()
            assert data == {"headers": expected_headers}

    def test_websocket_binary_json(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            message = await websocket.receive_json(mode="binary")
            await websocket.send_json(message, mode="binary")
            await websocket.close()

        client = test_client_factory(app)
        with client.websocket_connect("/123?a=abc") as websocket:
            websocket.send_json({"test": "data"}, mode="binary")
            data = websocket.receive_json(mode="binary")
            assert data == {"test": "data"}

    def test_websocket_ensure_unicode_on_send_json(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            message = await websocket.receive_json(mode="text")
            await websocket.send_json(message, mode="text")
            await websocket.close()

        client = test_client_factory(app)
        with client.websocket_connect("/123?a=abc") as websocket:
            websocket.send_json({"test": "数据"}, mode="text")
            data = websocket.receive_text()
            assert data == '{"test":"数据"}'

    def test_subprotocol(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            assert websocket["subprotocols"] == ["soap", "wamp"]
            await websocket.accept(subprotocol="wamp")
            await websocket.close()

        client = test_client_factory(app)
        with client.websocket_connect("/", subprotocols=["soap", "wamp"]) as websocket:
            assert websocket.accepted_subprotocol == "wamp"

    @pytest.mark.parametrize(
        ("accept_kwargs", "expected_headers"),
        [
            pytest.param({}, [], id="no_headers"),
            pytest.param({"headers": [(b"additional", b"header")]}, [(b"additional", b"header")], id="with_headers"),
        ],
    )
    def test_websocket_accept_headers(
            self,
            test_client_factory: TestClientFactory,
            accept_kwargs: dict[str, Any],
            expected_headers: list[tuple[bytes, bytes]],
    ) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept(**accept_kwargs)
            await websocket.close()

        client = test_client_factory(app)
        with client.websocket_connect("/") as websocket:
            assert websocket.extra_headers == expected_headers

    def test_websocket_scope_interface(self) -> None:
        async def mock_receive() -> Message:
            ...

        async def mock_send(message: Message) -> None: ...

        websocket = WebSocket(
            {"type": "websocket", "path": "/abc/", "headers": []},
            receive=mock_receive,
            send=mock_send,
        )
        assert websocket["type"] == "websocket"
        assert dict(websocket) == {"type": "websocket", "path": "/abc/", "headers": []}
        assert len(websocket) == 3

        assert websocket != WebSocket(
            {"type": "websocket", "path": "/abc/", "headers": []},
            receive=mock_receive,
            send=mock_send,
        )
        assert websocket == websocket
        assert websocket in {websocket}
        assert {websocket} == {websocket}


class TestWebSocketSendReceive:
    @pytest.mark.parametrize(
        ("send_name", "receive_name", "payload", "wrap"),
        [
            pytest.param("send_text", "receive_text", "Hello, world!", lambda data: "Message was: " + data, id="text"),
            pytest.param("send_bytes", "receive_bytes", b"Hello, world!", lambda data: b"Message was: " + data, id="bytes"),
            pytest.param("send_json", "receive_json", {"hello": "world"}, lambda data: {"message": data}, id="json"),
        ],
    )
    def test_websocket_send_and_receive(
            self,
            test_client_factory: TestClientFactory,
            send_name: str,
            receive_name: str,
            payload: Any,
            wrap: Any,
    ) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            data = await getattr(websocket, receive_name)()
            await getattr(websocket, send_name)(wrap(data))
            await websocket.close()

        client = test_client_factory(app)
        with client.websocket_connect("/") as websocket:
            getattr(websocket, send_name)(payload)
            assert getattr(websocket, receive_name)() == wrap(payload)

    @pytest.mark.parametrize(
        ("send_name", "iter_name", "receive_name", "payload", "wrap"),
        [
            pytest.param("send_text", "iter_text", "receive_text", "Hello, world!", lambda data: "Message was: " + data, id="text"),
            pytest.param("send_bytes", "iter_bytes", "receive_bytes", b"Hello, world!", lambda data: b"Message was: " + data, id="bytes"),
            pytest.param("send_json", "iter_json", "receive_json", {"hello": "world"}, lambda data: {"message": data}, id="json"),
        ],
    )
    def test_websocket_iter(
            self,
            test_client_factory: TestClientFactory,
            send_name: str,
            iter_name: str,
            receive_name: str,
            payload: Any,
            wrap: Any,
    ) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            async for data in getattr(websocket, iter_name)():
                await getattr(websocket, send_name)(wrap(data))

        client = test_client_factory(app)
        with client.websocket_connect("/") as websocket:
            getattr(websocket, send_name)(payload)
            assert getattr(websocket, receive_name)() == wrap(payload)

    def test_websocket_concurrency_pattern(self, test_client_factory: TestClientFactory) -> None:
        stream_send: ObjectSendStream[MutableMapping[str, Any]]
        stream_receive: ObjectReceiveStream[MutableMapping[str, Any]]
        stream_send, stream_receive = anyio.create_memory_object_stream()

        async def reader(websocket: WebSocket) -> None:
            async with stream_send:
                async for data in websocket.iter_json():
                    await stream_send.send(data)

        async def writer(websocket: WebSocket) -> None:
            async with stream_receive:
                async for message in stream_receive:
                    await websocket.send_json(message)

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            async with anyio.create_task_group() as task_group:
                task_group.start_soon(reader, websocket)
                await writer(websocket)
            await websocket.close()

        client = test_client_factory(app)
        with client.websocket_connect("/") as websocket:
            websocket.send_json({"hello": "world"})
            data = websocket.receive_json()
            assert data == {"hello": "world"}


class TestWebSocketLifecycle:
    def test_client_close(self, test_client_factory: TestClientFactory) -> None:
        close_code = None
        close_reason = None

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            nonlocal close_code, close_reason
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            try:
                await websocket.receive_text()
            except WebSocketDisconnect as exc:
                close_code = exc.code
                close_reason = exc.reason

        client = test_client_factory(app)
        with client.websocket_connect("/") as websocket:
            websocket.close(code=status.WS_1001_GOING_AWAY, reason="Going Away")
        assert close_code == status.WS_1001_GOING_AWAY
        assert close_reason == "Going Away"

    @pytest.mark.anyio
    async def test_client_disconnect_on_send(self) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            await websocket.send_text("Hello, world!")

        async def receive() -> Message:
            return {"type": "websocket.connect"}

        async def send(message: Message) -> None:
            if message["type"] == "websocket.accept":
                return
            raise OSError

        with pytest.raises(WebSocketDisconnect) as ctx:
            await app({"type": "websocket", "path": "/"}, receive, send)
        assert ctx.value.code == status.WS_1006_ABNORMAL_CLOSURE

    @pytest.mark.parametrize(
        ("close_kwargs", "expected_reason"),
        [
            pytest.param({"code": status.WS_1001_GOING_AWAY}, None, id="code_only"),
            pytest.param({"code": status.WS_1001_GOING_AWAY, "reason": "Going Away"}, "Going Away", id="code_and_reason"),
        ],
    )
    def test_websocket_close(
            self,
            test_client_factory: TestClientFactory,
            close_kwargs: dict[str, Any],
            expected_reason: str | None,
    ) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            await websocket.close(**close_kwargs)

        client = test_client_factory(app)
        with client.websocket_connect("/") as websocket:
            with pytest.raises(WebSocketDisconnect) as exc:
                websocket.receive_text()
            assert exc.value.code == status.WS_1001_GOING_AWAY
            if expected_reason is not None:
                assert exc.value.reason == expected_reason

    def test_rejected_connection(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            msg = await websocket.receive()
            assert msg == {"type": "websocket.connect"}
            await websocket.close(status.WS_1001_GOING_AWAY)

        client = test_client_factory(app)
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/"):
                pass
        assert exc.value.code == status.WS_1001_GOING_AWAY

    def test_websocket_exception(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            assert False

        client = test_client_factory(app)
        with pytest.raises(AssertionError):
            with client.websocket_connect("/123?a=abc"):
                pass

    def test_duplicate_close(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            await websocket.close()
            await websocket.close()

        client = test_client_factory(app)
        with pytest.raises(WebSocketDisconnected):
            with client.websocket_connect("/"):
                pass

    def test_duplicate_disconnect(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            message = await websocket.receive()
            assert message["type"] == "websocket.disconnect"
            await websocket.receive()

        client = test_client_factory(app)
        with pytest.raises(WebSocketDisconnected):
            with client.websocket_connect("/") as websocket:
                websocket.close()


class TestWebSocketDenialResponse:
    def _connect_expecting_denial_response(
            self, test_client_factory: TestClientFactory, app: Any
    ) -> WebSocketDenialResponse:
        client = test_client_factory(app)
        with pytest.raises(WebSocketDenialResponse) as exc:
            with client.websocket_connect("/"):
                pass
        return exc.value

    def test_send_denial_response(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            msg = await websocket.receive()
            assert msg == {"type": "websocket.connect"}
            await websocket.send_denial_response(Response(status_code=404, content="foo"))

        denial = self._connect_expecting_denial_response(test_client_factory, app)
        assert denial.status_code == 404
        assert denial.content == b"foo"

    def test_send_denial_response_with_streaming_response(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            message = await websocket.receive()
            assert message == {"type": "websocket.connect"}

            async def content() -> AsyncGenerator[bytes]:
                yield b"hello"
                yield b"world"

            await websocket.send_denial_response(StreamingResponse(content(), status_code=403))

        denial = self._connect_expecting_denial_response(test_client_factory, app)
        assert denial.status_code == 403
        assert denial.content == b"helloworld"

    def test_send_denial_response_with_file_response(
            self, test_client_factory: TestClientFactory, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "denial.txt"
        file_path.write_text("test content")

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            msg = await websocket.receive()
            assert msg == {"type": "websocket.connect"}
            await websocket.send_denial_response(FileResponse(file_path, status_code=401))

        denial = self._connect_expecting_denial_response(test_client_factory, app)
        assert denial.status_code == 401
        assert denial.content == b"test content"

    def test_send_response_multi(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            msg = await websocket.receive()
            assert msg == {"type": "websocket.connect"}
            await websocket.send(
                {
                    "type": "websocket.http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/plain"), (b"foo", b"bar")],
                }
            )
            await websocket.send({"type": "websocket.http.response.body", "body": b"hard", "more_body": True})
            await websocket.send({"type": "websocket.http.response.body", "body": b"body"})

        denial = self._connect_expecting_denial_response(test_client_factory, app)
        assert denial.status_code == 404
        assert denial.content == b"hardbody"
        assert denial.headers["foo"] == "bar"

    def test_send_response_unsupported(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            del scope["extensions"]["websocket.http.response"]
            websocket = WebSocket(scope, receive=receive, send=send)
            msg = await websocket.receive()
            assert msg == {"type": "websocket.connect"}
            response = Response(status_code=404, content="foo")
            with pytest.raises(
                    RuntimeError,
                    match="The server doesn't support the Websocket Denial Response extension.",
            ):
                await websocket.send_denial_response(response)
            await websocket.close()

        client = test_client_factory(app)
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/"):
                pass
        assert exc.value.code == status.WS_1000_NORMAL_CLOSURE

    def test_send_response_duplicate_start(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            msg = await websocket.receive()
            assert msg == {"type": "websocket.connect"}
            response = Response(status_code=404, content="foo")
            await websocket.send(
                {
                    "type": "websocket.http.response.start",
                    "status": response.status_code,
                    "headers": response.raw_headers,
                }
            )
            await websocket.send(
                {
                    "type": "websocket.http.response.start",
                    "status": response.status_code,
                    "headers": response.raw_headers,
                }
            )

        client = test_client_factory(app)
        with pytest.raises(
                RuntimeError,
                match=("Expected ASGI message \"websocket.http.response.body\", but got 'websocket.http.response.start'"),
        ):
            with client.websocket_connect("/"):
                pass


class TestWebSocketStateErrors:
    @pytest.mark.parametrize(
        "method_name",
        ["receive_text", "receive_bytes", "receive_json"],
        ids=["text", "bytes", "json"],
    )
    def test_receive_before_accept(self, test_client_factory: TestClientFactory, method_name: str) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await getattr(websocket, method_name)()

        client = test_client_factory(app)
        with pytest.raises(WebSocketDisconnected):
            with client.websocket_connect("/"):
                pass

    @pytest.mark.parametrize("operation", ["send", "receive"])
    def test_json_invalid_mode(self, test_client_factory: TestClientFactory, operation: str) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            if operation == "send":
                await websocket.send_json({}, mode="invalid")
            else:
                await websocket.receive_json(mode="invalid")

        client = test_client_factory(app)
        with pytest.raises(RuntimeError):
            with client.websocket_connect("/"):
                pass
    def test_send_before_accept(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.send({"type": "websocket.send"})

        client = test_client_factory(app)
        with pytest.raises(RuntimeError):
            with client.websocket_connect("/"):
                pass

    def test_send_wrong_message_type(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.send({"type": "websocket.accept"})
            await websocket.send({"type": "websocket.accept"})

        client = test_client_factory(app)
        with pytest.raises(RuntimeError):
            with client.websocket_connect("/"):
                pass

    def test_receive_after_client(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            websocket.client_state = WebSocketState.CONNECTING
            await websocket.receive()

        client = test_client_factory(app)
        with pytest.raises(RuntimeError):
            with client.websocket_connect("/") as websocket:
                websocket.send({"type": "websocket.send"})

    def test_receive_wrong_message_type(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            await websocket.receive()

        client = test_client_factory(app)
        with pytest.raises(RuntimeError):
            with client.websocket_connect("/") as websocket:
                websocket.send({"type": "websocket.connect"})