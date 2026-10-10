from collections.abc import Awaitable, Callable

import pytest

from speedy.application import Speedy
from speedy.exceptions import HTTPException
from speedy.middleware import Middleware
from speedy.middleware.base import BaseHTTPMiddleware
from speedy.middleware.body_limit import MAX_BODY_SIZE_SCOPE_KEY, RequestBodyLimitMiddleware
from speedy.requests import Request
from speedy.responses import PlainTextResponse, Response
from speedy.routing import Mount, Route, Router
from speedy.types import ASGIApplication, Message, Receive, Scope, Send
from tests.types import TestClientFactory


async def echo(request: Request) -> Response:
    return Response(await request.body())


class TestRequestBodyLimitMiddleware:
    def test_body_size_limit(self, test_client_factory: TestClientFactory) -> None:
        app = RequestBodyLimitMiddleware(
            Speedy(routes=[Route("/", echo, methods=["POST"])]),
            max_body_size=5,
        )
        client = test_client_factory(app)

        response = client.post("/", content=b"12345")
        assert response.status_code == 200
        assert response.content == b"12345"

        response = client.post("/", content=b"123456")
        assert response.status_code == 413
        assert response.text == "Content Too Large"

    def test_received_bytes_are_counted_with_unreliable_content_length(
            self, test_client_factory: TestClientFactory
    ) -> None:
        app = RequestBodyLimitMiddleware(
            Speedy(routes=[Route("/", echo, methods=["POST"])]),
            max_body_size=5,
        )
        client = test_client_factory(app)

        response = client.post("/", content=b"123456", headers={"Content-Length": "1"})
        assert response.status_code == 413
        assert response.text == "Content Too Large"
        response = client.post("/", content=b"12345", headers={"Content-Length": "invalid"})

        assert response.status_code == 200
        assert response.content == b"12345"

    @pytest.mark.anyio
    async def test_content_length_rejects_before_receiving_body(self) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            await receive()

        async def receive() -> Message:
            raise AssertionError("receive should not be called")

        sent: list[Message] = []

        async def send(message: Message) -> None:
            sent.append(message)

        scope: Scope = {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"content-length", b"6")],
        }
        middleware = RequestBodyLimitMiddleware(app, max_body_size=5)

        await middleware(scope, receive, send)
        assert sent[0]["status"] == 413

    @pytest.mark.anyio
    async def test_received_bytes_are_counted_without_content_length(self) -> None:
        messages = iter(
            [
                {"type": "http.request", "body": b"123", "more_body": True},
                {"type": "http.request", "body": b"456", "more_body": False},
            ]
        )

        async def receive() -> Message:
            return next(messages)

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            await receive()
            await receive()

        sent: list[Message] = []

        async def send(message: Message) -> None:
            sent.append(message)

        scope: Scope = {"type": "http", "method": "POST", "path": "/", "headers": []}
        middleware = RequestBodyLimitMiddleware(app, max_body_size=5)

        await middleware(scope, receive, send)
        assert sent[0]["status"] == 413

    @pytest.mark.anyio
    async def test_limit_exceeded_after_response_started_is_raised(self) -> None:
        messages = iter(
            [
                {"type": "http.request", "body": b"12345", "more_body": True},
                {"type": "http.request", "body": b"6", "more_body": False},
            ]
        )

        async def receive() -> Message:
            return next(messages)

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await receive()
            await receive()

        async def send(message: Message) -> None:
            pass

        scope: Scope = {"type": "http", "method": "POST", "path": "/", "headers": []}
        middleware = RequestBodyLimitMiddleware(app, max_body_size=5)

        with pytest.raises(HTTPException) as exc_info:
            await middleware(scope, receive, send)

        assert exc_info.value.status_code == 413

    @pytest.mark.anyio
    async def test_non_http_scope_is_unchanged(self) -> None:
        received_scope: Scope | None = None

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            nonlocal received_scope
            received_scope = scope

        async def receive() -> Message:
            return {"type": "lifespan.startup"}

        async def send(message: Message) -> None:
            pass

        scope: Scope = {"type": "lifespan"}
        middleware = RequestBodyLimitMiddleware(app, max_body_size=5)

        await middleware(scope, receive, send)

        assert received_scope is scope
        assert MAX_BODY_SIZE_SCOPE_KEY not in scope

    @pytest.mark.anyio
    async def test_non_request_message_passes_through(self) -> None:
        message: Message = {"type": "http.disconnect"}
        received: Message | None = None

        async def receive() -> Message:
            return message

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            nonlocal received
            received = await receive()

        async def send(message: Message) -> None:
            pass

        scope: Scope = {"type": "http", "method": "POST", "path": "/", "headers": []}
        middleware = RequestBodyLimitMiddleware(app, max_body_size=5)

        await middleware(scope, receive, send)

        assert received is message

    @pytest.mark.anyio
    async def test_existing_scope_limit_is_restored(self) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            assert scope[MAX_BODY_SIZE_SCOPE_KEY] == 5

        async def receive() -> Message:
            return {"type": "http.request", "body": b""}

        async def send(message: Message) -> None:
            pass

        scope: Scope = {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
            MAX_BODY_SIZE_SCOPE_KEY: 10,
        }
        middleware = RequestBodyLimitMiddleware(app, max_body_size=5)

        await middleware(scope, receive, send)

        assert scope[MAX_BODY_SIZE_SCOPE_KEY] == 10


class TestSpeedyBodyLimit:
    def test_content_length_is_checked_without_reading_body(
            self, test_client_factory: TestClientFactory
    ) -> None:
        async def endpoint(request: Request) -> PlainTextResponse:
            return PlainTextResponse("response")

        app = Speedy(
            routes=[Route("/", endpoint, methods=["POST"])],
            max_body_size=5,
        )
        client = test_client_factory(app)

        response = client.post("/", content=b"123456")
        assert response.status_code == 413
        assert response.text == "Content Too Large"

    def test_speedy_limit_applies_before_user_middleware(
            self, test_client_factory: TestClientFactory
    ) -> None:
        class ReadBodyMiddleware:
            def __init__(self, app: ASGIApplication) -> None:
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                await receive()
                await self.app(scope, receive, send)

        app = Speedy(
            routes=[Route("/", echo, methods=["POST"])],
            middleware=[Middleware(ReadBodyMiddleware)],
            max_body_size=5,
        )
        client = test_client_factory(app)

        response = client.post("/", content=b"123456")
        assert response.status_code == 413

    def test_multipart_file_counts_towards_limit(self, test_client_factory: TestClientFactory) -> None:
        async def upload(request: Request) -> PlainTextResponse:
            async with request.form():
                return PlainTextResponse("uploaded")

        app = Speedy(
            routes=[Route("/", upload, methods=["POST"])],
            max_body_size=512,
        )
        client = test_client_factory(app)
        response = client.post("/", files={"file": ("example.txt", b"x" * 1024)})
        assert response.status_code == 413


class TestRouteBodyLimit:
    def test_route_override_applies_when_middleware_defers_response_start(
            self, test_client_factory: TestClientFactory
    ) -> None:
        async def endpoint(request: Request) -> PlainTextResponse:
            return PlainTextResponse("response")

        async def passthrough(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
            return await call_next(request)

        app = Speedy(
            routes=[Route("/", endpoint, methods=["POST"], max_body_size=10)],
            middleware=[Middleware(BaseHTTPMiddleware, dispatch=passthrough)],
            max_body_size=5,
        )
        client = test_client_factory(app)

        response = client.post("/", content=b"12345678")
        assert response.status_code == 200
        assert response.text == "response"

    def test_route_can_raise_application_limit(self, test_client_factory: TestClientFactory) -> None:
        app = Speedy(
            routes=[
                Route("/default", echo, methods=["POST"]),
                Route("/upload", echo, methods=["POST"], max_body_size=10),
            ],
            max_body_size=5,
        )
        client = test_client_factory(app)

        default_response = client.post("/default", content=b"12345678")
        upload_response = client.post("/upload", content=b"12345678")

        assert default_response.status_code == 413
        assert upload_response.status_code == 200
        assert upload_response.content == b"12345678"

    def test_route_can_lower_application_limit(self, test_client_factory: TestClientFactory) -> None:
        app = Speedy(
            routes=[Route("/", echo, methods=["POST"], max_body_size=5)],
            max_body_size=10,
        )
        client = test_client_factory(app)

        response = client.post("/", content=b"123456")
        assert response.status_code == 413

    def test_route_override_survives_shallow_scope_copy(self, test_client_factory: TestClientFactory) -> None:
        class CopyScopeMiddleware:
            def __init__(self, app: ASGIApplication) -> None:
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                await self.app(dict(scope), receive, send)

        app = Speedy(
            routes=[Route("/", echo, methods=["POST"], max_body_size=10)],
            middleware=[Middleware(CopyScopeMiddleware)],
            max_body_size=5,
        )
        client = test_client_factory(app)

        response = client.post("/", content=b"12345678")
        assert response.status_code == 200
        assert response.content == b"12345678"

    def test_stricter_route_rejects_body_read_by_middleware(self, test_client_factory: TestClientFactory) -> None:
        async def read_body(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
            await request.body()
            return await call_next(request)

        app = Speedy(
            routes=[Route("/", echo, methods=["POST"], max_body_size=5)],
            middleware=[Middleware(BaseHTTPMiddleware, dispatch=read_body)],
            max_body_size=10,
        )
        client = test_client_factory(app)

        response = client.post("/", content=b"123456")
        assert response.status_code == 413


class TestMountAndRouterBodyLimit:
    def test_mount_can_override_application_limit(self, test_client_factory: TestClientFactory) -> None:
        app = Speedy(
            routes=[
                Mount(
                    "/upload",
                    routes=[Route("/", echo, methods=["POST"])],
                    max_body_size=10,
                )
            ],
            max_body_size=5,
        )
        client = test_client_factory(app)

        response = client.post("/upload/", content=b"12345678")
        assert response.status_code == 200
        assert response.content == b"12345678"

    def test_router_limit(self, test_client_factory: TestClientFactory) -> None:
        app = Router(routes=[Route("/", echo, methods=["POST"])], max_body_size=5)
        client = test_client_factory(app)

        response = client.post("/", content=b"123456")
        assert response.status_code == 413
