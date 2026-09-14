import contextlib
import io
import json
import math
from collections.abc import Awaitable, Callable, Generator, Iterable, Mapping, Sequence
from concurrent.futures import Future
from contextlib import AbstractContextManager
from typing import Any, Literal, Self, TypedDict, cast
from urllib.parse import unquote, urljoin

import anyio
import httpx2
from anyio.streams.stapled import StapledObjectStream

from speedy.exceptions import WebSocketDisconnect
from speedy.types import Message, Receive, Scope, Send

_PortalFactoryType = Callable[[], AbstractContextManager[anyio.from_thread.BlockingPortal]]

ASGI3App = Callable[[Scope, Receive, Send], Awaitable[None]]

_RequestData = Mapping[str, str | Iterable[str] | bytes]

_DEFAULT_PORTS = {"http": 80, "ws": 80, "https": 443, "wss": 443}


class _AsyncBackend(TypedDict):
    backend: str
    backend_options: dict[str, Any]


class _Upgrade(Exception):
    def __init__(self, session: "WebSocketTestSession") -> None:
        self.session = session


class WebSocketDenialResponse(
    httpx2.Response,
    WebSocketDisconnect,
):
    """
    A special case of `WebSocketDisconnect`, raised in the `TestClient` if the
    `WebSocket` is closed before being accepted with a `send_denial_response()`.
    """


class WebSocketTestSession:
    def __init__(
        self,
        app: ASGI3App,
        scope: Scope,
        portal_factory: _PortalFactoryType,
    ) -> None:
        self.app = app
        self.scope = scope
        self.accepted_subprotocol: str | None = None
        self.extra_headers: list[tuple[bytes, bytes]] | None = None
        self.portal_factory = portal_factory

    def __enter__(self) -> Self:
        with contextlib.ExitStack() as stack:
            self.portal = portal = stack.enter_context(self.portal_factory())
            fut, cs = portal.start_task(self._run)
            stack.callback(fut.result)
            stack.callback(portal.call, cs.cancel)
            self.send({"type": "websocket.connect"})
            message = self.receive()
            self._raise_on_close(message)
            self.accepted_subprotocol = message.get("subprotocol", None)
            self.extra_headers = message.get("headers", None)
            stack.callback(self.close, 1000)
            self.exit_stack = stack.pop_all()
            return self

    def __exit__(self, *args: Any) -> bool | None:
        return self.exit_stack.__exit__(*args)

    async def _run(self, *, task_status: anyio.abc.TaskStatus[anyio.CancelScope]) -> None:
        send_tx, send_rx = anyio.create_memory_object_stream[Message](math.inf)
        receive_tx, receive_rx = anyio.create_memory_object_stream[Message](math.inf)
        with send_tx, send_rx, receive_tx, receive_rx, anyio.CancelScope() as cs:
            self._receive_tx = receive_tx
            self._send_rx = send_rx
            task_status.started(cs)
            await self.app(self.scope, receive_rx.receive, send_tx.send)

            await anyio.sleep_forever()

    def send(self, message: Message) -> None:
        self.portal.call(self._receive_tx.send, message)

    def send_text(self, data: str) -> None:
        self.send({"type": "websocket.receive", "text": data})

    def send_bytes(self, data: bytes) -> None:
        self.send({"type": "websocket.receive", "bytes": data})

    def send_json(self, data: Any, mode: Literal["text", "binary"] = "text") -> None:
        text = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        if mode == "text":
            self.send({"type": "websocket.receive", "text": text})
        else:
            self.send({"type": "websocket.receive", "bytes": text.encode("utf-8")})

    def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.send({"type": "websocket.disconnect", "code": code, "reason": reason})

    def receive(self) -> Message:
        return self.portal.call(self._send_rx.receive)

    def receive_text(self) -> str:
        message = self.receive()
        self._raise_on_close(message)
        return cast(str, message["text"])

    def receive_bytes(self) -> bytes:
        message = self.receive()
        self._raise_on_close(message)
        return cast(bytes, message["bytes"])

    def receive_json(self, mode: Literal["text", "binary"] = "text") -> Any:
        message = self.receive()
        self._raise_on_close(message)
        text = message["text"] if mode == "text" else message["bytes"].decode("utf-8")
        return json.loads(text)

    def _raise_on_close(self, message: Message) -> None:
        if message["type"] == "websocket.close":
            raise WebSocketDisconnect(code=message.get("code", 1000), reason=message.get("reason", ""))
        elif message["type"] == "websocket.http.response.start":
            status_code: int = message["status"]
            headers: list[tuple[bytes, bytes]] = message["headers"]
            body: list[bytes] = []
            while True:
                message = self.receive()
                if message["type"] != "websocket.http.response.body":
                    raise RuntimeError(f'Expected "websocket.http.response.body", got: {message["type"]!r}')
                body.append(message["body"])
                if not message.get("more_body", False):
                    break
            raise WebSocketDenialResponse(status_code=status_code, headers=headers, content=b"".join(body))


class _TestClientTransport(httpx2.BaseTransport):
    def __init__(
        self,
        app: ASGI3App,
        portal_factory: _PortalFactoryType,
        raise_server_exceptions: bool = True,
        root_path: str = "",
        *,
        client: tuple[str, int],
        app_state: dict[str, Any],
    ) -> None:
        self.app = app
        self.raise_server_exceptions = raise_server_exceptions
        self.root_path = root_path
        self.portal_factory = portal_factory
        self.app_state = app_state
        self.client = client

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        scheme = request.url.scheme
        host = request.url.raw_host.decode(encoding="ascii")
        path = request.url.path
        raw_path = request.url.raw_path
        query = request.url.query.decode(encoding="ascii")

        port = request.url.port
        if port is None:
            port = _DEFAULT_PORTS[scheme]

        host_header = [] if "host" in request.headers else [(b"host", request.url.netloc)]
        headers = host_header + [(key.lower().encode(), value.encode()) for key, value in request.headers.multi_items()]

        scope: dict[str, Any]

        if scheme in {"ws", "wss"}:
            subprotocol = request.headers.get("sec-websocket-protocol", None)
            if subprotocol is None:
                subprotocols: Sequence[str] = []
            else:
                subprotocols = [value.strip() for value in subprotocol.split(",")]
            scope = {
                "type": "websocket",
                "path": unquote(path),
                "raw_path": raw_path.split(b"?", 1)[0],
                "root_path": self.root_path,
                "scheme": scheme,
                "query_string": query.encode(),
                "headers": headers,
                "client": self.client,
                "server": [host, port],
                "subprotocols": subprotocols,
                "state": self.app_state.copy(),
                "extensions": {"websocket.http.response": {}},
            }
            session = WebSocketTestSession(self.app, scope, self.portal_factory)
            raise _Upgrade(session)

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": request.method,
            "path": unquote(path),
            "raw_path": raw_path.split(b"?", 1)[0],
            "root_path": self.root_path,
            "scheme": scheme,
            "query_string": query.encode(),
            "headers": headers,
            "client": self.client,
            "server": [host, port],
            "extensions": {"http.response.debug": {}},
            "state": self.app_state.copy(),
        }

        request_complete = False
        response_started = False
        response_complete: anyio.Event
        raw_kwargs: dict[str, Any] = {"stream": io.BytesIO()}
        debug_info: dict[str, Any] | None = None

        async def receive() -> Message:
            nonlocal request_complete

            if request_complete:
                if not response_complete.is_set():
                    await response_complete.wait()
                return {"type": "http.disconnect"}

            body_bytes = request.read()
            request_complete = True
            return {"type": "http.request", "body": body_bytes}

        async def send(message: Message) -> None:
            nonlocal raw_kwargs, response_started, debug_info

            if message["type"] == "http.response.start":
                if response_started:
                    raise RuntimeError('Received multiple "http.response.start" messages.')
                raw_kwargs["status_code"] = message["status"]
                raw_kwargs["headers"] = [(key.decode(), value.decode()) for key, value in message.get("headers", [])]
                response_started = True
            elif message["type"] == "http.response.body":
                if not response_started:
                    raise RuntimeError('Received "http.response.body" without "http.response.start".')
                if response_complete.is_set():
                    raise RuntimeError('Received "http.response.body" after response completed.')
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if request.method != "HEAD":
                    raw_kwargs["stream"].write(body)
                if not more_body:
                    raw_kwargs["stream"].seek(0)
                    response_complete.set()
            elif message["type"] == "http.response.debug":
                debug_info = message["info"]

        try:
            with self.portal_factory() as portal:
                response_complete = portal.call(anyio.Event)
                portal.call(self.app, scope, receive, send)
        except BaseException:
            if self.raise_server_exceptions:
                raise

        if self.raise_server_exceptions and not response_started:
            raise RuntimeError("TestClient did not receive any response.")
        elif not response_started:
            raw_kwargs = {
                "status_code": 500,
                "headers": [],
                "stream": io.BytesIO(),
            }

        raw_kwargs["stream"] = httpx2.ByteStream(raw_kwargs["stream"].read())

        response = httpx2.Response(**raw_kwargs, request=request)
        if debug_info is not None:
            response.extensions["http.response.debug"] = debug_info
            if "template" in debug_info:
                response.template = debug_info["template"]
            if "context" in debug_info:
                response.context = debug_info["context"]
        return response


class TestClient(httpx2.Client):
    __test__ = False
    task: Future[None]
    portal: anyio.from_thread.BlockingPortal | None = None

    def __init__(
        self,
        app: ASGI3App,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        root_path: str = "",
        backend: Literal["asyncio", "trio"] = "asyncio",
        backend_options: dict[str, Any] | None = None,
        cookies: httpx2._types.CookieTypes | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
        client: tuple[str, int] = ("testclient", 50000),
    ) -> None:
        self.async_backend = _AsyncBackend(backend=backend, backend_options=backend_options or {})
        self.app: ASGI3App = app
        self.app_state: dict[str, Any] = {}
        transport = _TestClientTransport(
            self.app,
            portal_factory=self._portal_factory,
            raise_server_exceptions=raise_server_exceptions,
            root_path=root_path,
            app_state=self.app_state,
            client=client,
        )
        if headers is None:
            headers = {}
        headers.setdefault("user-agent", "testclient")
        super().__init__(
            base_url=base_url,
            headers=headers,
            transport=transport,
            follow_redirects=follow_redirects,
            cookies=cookies,
        )

    @contextlib.contextmanager
    def _portal_factory(self) -> Generator[anyio.from_thread.BlockingPortal, None, None]:
        if self.portal is not None:
            yield self.portal
        else:
            with anyio.from_thread.start_blocking_portal(**self.async_backend) as portal:
                yield portal

    def websocket_connect(
        self,
        url: str,
        subprotocols: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> WebSocketTestSession:
        url = urljoin("ws://testserver", url)
        headers = kwargs.get("headers", {})
        headers.setdefault("connection", "upgrade")
        headers.setdefault("sec-websocket-key", "testserver==")
        headers.setdefault("sec-websocket-version", "13")
        if subprotocols is not None:
            headers.setdefault("sec-websocket-protocol", ", ".join(subprotocols))
        kwargs["headers"] = headers
        try:
            super().request("GET", url, **kwargs)
        except _Upgrade as exc:
            return exc.session
        raise RuntimeError("Expected WebSocket upgrade")

    def __enter__(self) -> Self:
        with contextlib.ExitStack() as stack:
            self.portal = portal = stack.enter_context(anyio.from_thread.start_blocking_portal(**self.async_backend))

            @stack.callback
            def reset_portal() -> None:
                self.portal = None

            send = anyio.create_memory_object_stream[Message | None](math.inf)
            receive = anyio.create_memory_object_stream[Message](math.inf)
            for channel in (*send, *receive):
                stack.callback(channel.close)
            self.stream_send = StapledObjectStream(*send)
            self.stream_receive = StapledObjectStream(*receive)
            self.task = portal.start_task_soon(self.lifespan)
            portal.call(self.wait_startup)

            @stack.callback
            def wait_shutdown() -> None:
                portal.call(self.wait_shutdown)

            self.exit_stack = stack.pop_all()

        return self

    def __exit__(self, *args: Any) -> None:
        self.exit_stack.close()

    async def lifespan(self) -> None:
        scope = {"type": "lifespan", "state": self.app_state}
        try:
            await self.app(scope, self.stream_receive.receive, self.stream_send.send)
        finally:
            await self.stream_send.send(None)

    async def wait_startup(self) -> None:
        await self.stream_receive.send({"type": "lifespan.startup"})

        message = await self._receive_lifespan_message()
        if message["type"] not in ("lifespan.startup.complete", "lifespan.startup.failed"):
            raise RuntimeError(f"Unexpected message during lifespan startup: {message['type']!r}")
        if message["type"] == "lifespan.startup.failed":
            await self._receive_lifespan_message()

    async def wait_shutdown(self) -> None:
        await self.stream_receive.send({"type": "lifespan.shutdown"})
        message = await self._receive_lifespan_message()
        if message["type"] not in ("lifespan.shutdown.complete", "lifespan.shutdown.failed"):
            raise RuntimeError(f"Unexpected message during lifespan shutdown: {message['type']!r}")
        if message["type"] == "lifespan.shutdown.failed":
            await self._receive_lifespan_message()

    async def _receive_lifespan_message(self) -> Message:
        message = await self.stream_send.receive()
        if message is None:
            self.task.result()
        return cast(Message, message)
