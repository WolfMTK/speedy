from __future__ import annotations

import asyncio
from io import BytesIO
from types import GeneratorType
from typing import TYPE_CHECKING, TypeVar, Generic, TypedDict, Any, cast
from urllib.parse import unquote

from httpx import AsyncBaseTransport, Response, ByteStream, BaseTransport

from speedy.status_code import HTTP_500_INTERNAL_SERVER_ERROR

if TYPE_CHECKING:
    from httpx import Request

    from speedy.testing.client import TestClient
    from speedy.types import (
        Receive,
        ASGIReceiveEvent,
        Send,
        WebSocketScope,
    )

T = TypeVar("T", bound="TestClient")


class ConnectionUpgradeExceptionError(Exception):
    def __init__(self, scope: WebSocketScope) -> None:
        self.scope = scope


class SendReceiveContext(TypedDict):
    request_complete: bool
    response_complete: asyncio.Event
    raw_kwargs: dict[str, Any,]
    response_started: bool
    template: str | None
    context: Any | None


class TestClientTransport(AsyncBaseTransport, Generic[T]):
    def __init__(
            self,
            client: T,
            raise_server_exceptions: bool = False,
            root_path: str = "",
    ) -> None:
        self.client = client
        self.raise_server_exceptions = raise_server_exceptions
        self.root_path = root_path

    @staticmethod
    def create_receive(request: Request, context: SendReceiveContext) -> Receive:
        body_source = cast("bytes | str | GeneratorType", request.read() or b"")
        is_generator = isinstance(body_source, GeneratorType)
        generator = body_source if is_generator else None

        async def receive() -> ASGIReceiveEvent:
            if context["request_complete"]:
                if not context["response_complete"].is_set():
                    await context["response_complete"].wait()
                return cast("ASGIReceiveEvent", {"type": "http.disconnect"})
            context["request_complete"] = True
            body: bytes = b""
            more_body: bool = False
            if is_generator:
                try:
                    chunk = next(generator)
                    body = chunk if isinstance(chunk, bytes) else chunk.encode("utf-8")
                    more_body = True
                    context["request_complete"] = False
                except StopIteration:
                    pass
            else:
                body = body_source if isinstance(body_source, bytes) else body_source.encode("utf-8")
            return cast(
                "ASGIReceiveEvent", {
                    "type": "http.request",
                    "body": body,
                    "more_body": more_body,
                },
            )

        return receive

    @staticmethod
    def create_send(request: Request, context: SendReceiveContext) -> Send:
        raw_kwargs = context["raw_kwargs"]
        stream = raw_kwargs["stream"]

        async def send(message: ASGIReceiveEvent) -> None:
            msg_type = message["type"]

            if msg_type == "http.response.start":
                if context["response_started"]:
                    raise AssertionError('Received multiple "http.response.start" messages.')
                raw_kwargs["status_code"] = message["status"]
                raw_kwargs["headers"] = [
                    (k.decode("latin1"), v.decode("latin1"))
                    for k, v in message.get("headers", [])
                ]
                context["response_started"] = True
            elif msg_type == "http.response.body":
                if not context["response_started"]:
                    raise AssertionError('Received "http.response.body" without "http.response.start".')
                if context["response_complete"].is_set():
                    raise AssertionError('Received "http.response.body" after response completed.')

                body = message.get("body", b"")
                more_body = message.get("more_body", False)

                if request.method != "HEAD":
                    stream.write(body)

                if not more_body:
                    stream.seek(0)
                    context["response_complete"].set()
                return
            elif msg_type == "http.response.template":
                context["template"] = message["template"]
                context["context"] = message["context"]
                return

        return send

    def parse_request(self, request: Request) -> dict[str, Any]:
        url = request.url
        scheme = url.scheme
        default_port = 443 if scheme in {"https", "wss"} else 80
        host = url.host
        port = url.port if url.port is not None else default_port
        raw_path = url.raw_path
        if b"?" in raw_path:
            raw_path = raw_path[: raw_path.index(b"?")]
        path = unquote(url.path)
        host_header = request.headers.get("host") or (
            host if port == default_port else f"{host}:{port}"
        )
        headers = [
            (b"host", host_header.encode("latin1")),
            *[
                (k.lower().encode("latin1"), v.encode("latin1"))
                for k, v in request.headers.items()
                if k.lower() != "host"
            ],
        ]
        scope_type = "websocket" if scheme in {"ws", "wss"} else "http"
        scope = {
            "type": scope_type,
            "path": path,
            "raw_path": raw_path,
            "root_path": self.root_path,
            "scheme": scheme,
            "query_string": url.query,
            "headers": headers,
            "client": ("testclient", 50000),
            "server": (host, port),
        }
        if scope_type == "websocket":
            protocols = request.headers.get("sec-websocket-protocol", "")
            subprotocols = [p.strip() for p in protocols.split(",") if p.strip()]
            scope["subprotocols"] = subprotocols
        return scope

    async def handle_async_request(self, request: Request) -> Response:
        scope = self.parse_request(request)
        if scope["type"] == "websocket":
            raise ConnectionUpgradeExceptionError(cast("WebSocketScope", scope))

        scope.update(
            method=request.method,
            http_version="1.1",
            extensions={"http.response.template": {}},
        )

        stream = BytesIO()
        response_complete = asyncio.Event()
        context: SendReceiveContext = {
            "response_complete": response_complete,
            "request_complete": False,
            "raw_kwargs": {"stream": stream},
            "response_started": False,
            "template": None,
            "context": None,
        }
        try:
            await self.client.app(
                scope,
                self.create_receive(request, context),
                self.create_send(request, context),
            )
        except BaseException as err:
            if self.raise_server_exceptions:
                raise err
            return Response(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                headers=[],
                stream=ByteStream(stream.read()),
                request=request,
            )

        if not context["response_started"]:
            if self.raise_server_exceptions:
                raise AssertionError("TestClient did not receive any response.")
            return Response(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                headers=[],
                stream=ByteStream(stream.read()),
                request=request,
            )
        final_stream = ByteStream(stream.read())
        response = Response(
            status_code=context["raw_kwargs"]["status_code"],
            headers=context["raw_kwargs"]["headers"],
            stream=final_stream,
            request=request,
        )

        response.template = context["template"]
        response.context = context["context"]
        return response


class SyncTestClientTransport(BaseTransport):
    def __init__(
            self,
            client: TestClient,
            raise_server_exceptions: bool = True,
            root_path: str = "",
    ) -> None:
        self.client = client
        self._async_transport = TestClientTransport(
            client=client,
            raise_server_exceptions=raise_server_exceptions,
            root_path=root_path,
        )

    def handle_request(self, request: Request) -> Response:
        return self.client.blocking_portal.call(self._async_transport.handle_async_request, request)
