import itertools
from asyncio import Task, current_task as asyncio_current_task
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import anyio
import pytest
import sniffio
import trio
from speedy.application import Speedy
from speedy.exceptions import WebSocketDisconnect
from speedy.middleware import Middleware
from speedy.requests import Request
from speedy.responses import JSONResponse, RedirectResponse, Response
from speedy.routing import Route
from speedy.testclient import TestClient
from speedy.types import ASGIApplication, Receive, Scope, Send
from speedy.websocket import WebSocket
from tests.types import TestClientFactory


def mock_service_endpoint(request: Request) -> JSONResponse:
    return JSONResponse({"mock": "example"})


mock_service = Speedy(routes=[Route("/", endpoint=mock_service_endpoint)])


def current_task() -> Task[Any] | trio.lowlevel.Task:
    asynclib_name = sniffio.current_async_library()
    if asynclib_name == "trio":
        return trio.lowlevel.current_task()
    if asynclib_name == "asyncio":
        task = asyncio_current_task()
        if task is None:
            raise RuntimeError("must be called from a running task")
        return task
    raise RuntimeError(f"unsupported asynclib={asynclib_name}")


def make_debug_app(info: dict[str, Any] | None = None) -> ASGIApplication:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": [[b"content-type", b"text/plain"]]})
        if info is not None:
            await send({"type": "http.response.debug", "info": info})
        await send({"type": "http.response.body", "body": b"Hello, world!"})

    return app


async def client_info_app(scope: Scope, receive: Receive, send: Send) -> None:
    client = scope.get("client")
    assert client is not None
    host, port = client
    response = JSONResponse({"host": host, "port": port})
    await response(scope, receive, send)


async def redirect_app(scope: Scope, receive: Receive, send: Send) -> None:
    if "/ok" in scope["path"]:
        response = Response("ok")
    else:
        response = RedirectResponse("/ok")
    await response(scope, receive, send)


class TestTestClient:
    def test_use_testclient_in_endpoint(self, test_client_factory: TestClientFactory) -> None:
        def homepage(request: Request) -> JSONResponse:
            client = test_client_factory(mock_service)
            response = client.get("/")
            return JSONResponse(response.json())

        app = Speedy(routes=[Route("/", endpoint=homepage)])

        client = test_client_factory(app)
        response = client.get("/")
        assert response.json() == {"mock": "example"}

    def test_testclient_headers_behavior(self) -> None:
        client = TestClient(mock_service)
        assert client.headers.get("user-agent") == "testclient"

        client = TestClient(mock_service, headers={"user-agent": "non-default-agent"})
        assert client.headers.get("user-agent") == "non-default-agent"

        client = TestClient(mock_service, headers={"Authentication": "Bearer 123"})
        assert client.headers.get("user-agent") == "testclient"
        assert client.headers.get("Authentication") == "Bearer 123"

    @pytest.mark.parametrize(
        ("client_kwargs", "expected"),
        [
            ({}, {"host": "testclient", "port": 50000}),
            ({"client": ("192.168.0.1", 3000)}, {"host": "192.168.0.1", "port": 3000}),
        ],
        ids=("default", "custom"),
    )
    def test_client(
            self,
            test_client_factory: TestClientFactory,
            client_kwargs: dict[str, Any],
            expected: dict[str, Any],
    ) -> None:
        client = test_client_factory(client_info_app, **client_kwargs)
        response = client.get("/")
        assert response.json() == expected

    def test_use_testclient_as_contextmanager(self, test_client_factory: TestClientFactory) -> None:
        counter = itertools.count()
        identity_runvar = anyio.lowlevel.RunVar[int]("identity_runvar")

        def get_identity() -> int:
            try:
                return identity_runvar.get()
            except LookupError:
                token = next(counter)
                identity_runvar.set(token)
                return token

        startup_task = object()
        startup_loop = None
        shutdown_task = object()
        shutdown_loop = None

        @asynccontextmanager
        async def lifespan_context(app: Speedy) -> AsyncGenerator[None, None]:
            nonlocal startup_task, startup_loop, shutdown_task, shutdown_loop

            startup_task = current_task()
            startup_loop = get_identity()
            async with anyio.create_task_group():
                yield
            shutdown_task = current_task()
            shutdown_loop = get_identity()

        async def loop_id(request: Request) -> JSONResponse:
            return JSONResponse(get_identity())

        app = Speedy(
            lifespan=lifespan_context,
            routes=[Route("/loop_id", endpoint=loop_id)],
        )

        client = test_client_factory(app)

        with client:
            assert client.get("/loop_id").json() == 0
            assert client.get("/loop_id").json() == 0

        assert startup_loop == 0
        assert shutdown_loop == 0
        assert startup_task is shutdown_task

        assert client.get("/loop_id").json() == 1
        assert client.get("/loop_id").json() == 2

        first_task = startup_task

        with client:
            assert client.get("/loop_id").json() == 3
            assert client.get("/loop_id").json() == 3

        assert startup_loop == 3
        assert shutdown_loop == 3
        assert startup_task is shutdown_task
        assert first_task is not startup_task

    def test_error_on_startup(self, test_client_factory: TestClientFactory) -> None:
        @asynccontextmanager
        async def lifespan(app: Speedy) -> AsyncGenerator[None, None]:
            raise RuntimeError("Startup error")
            yield

        startup_error_app = Speedy(lifespan=lifespan)

        with pytest.raises(RuntimeError, match="Startup error"):
            with test_client_factory(startup_error_app):
                pass

    def test_exception_in_middleware(self, test_client_factory: TestClientFactory) -> None:
        class MiddlewareException(Exception):
            pass

        class BrokenMiddleware:
            def __init__(self, app: ASGIApplication):
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                raise MiddlewareException()

        broken_middleware = Speedy(middleware=[Middleware(BrokenMiddleware)])

        with pytest.raises(MiddlewareException):
            with test_client_factory(broken_middleware):
                pass

    def test_testclient_asgi3(self, test_client_factory: TestClientFactory) -> None:
        client = test_client_factory(make_debug_app())
        response = client.get("/")
        assert response.text == "Hello, world!"

    def test_debug_info_in_response_extensions(self, test_client_factory: TestClientFactory) -> None:
        info = {"fragment": "header", "blocks": ["nav", "title"]}

        client = test_client_factory(make_debug_app(info))
        response = client.get("/")
        assert response.extensions["http.response.debug"] == info
        assert not hasattr(response, "template")

    def test_debug_info_in_response_extensions_with_template(self, test_client_factory: TestClientFactory) -> None:
        info = {"template": "index.html", "context": {"name": "world"}, "blocks": ["nav"]}

        client = test_client_factory(make_debug_app(info))
        response = client.get("/")
        assert response.extensions["http.response.debug"] == info
        assert response.template == "index.html"
        assert response.context == {"name": "world"}

    def test_websocket_blocking_receive(self, test_client_factory: TestClientFactory) -> None:
        async def respond(websocket: WebSocket) -> None:
            await websocket.send_json({"message": "test"})

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            async with anyio.create_task_group() as task_group:
                task_group.start_soon(respond, websocket)
                try:
                    await websocket.receive_json()
                except WebSocketDisconnect:
                    pass

        client = test_client_factory(app)
        with client.websocket_connect("/") as websocket:
            data = websocket.receive_json()
            assert data == {"message": "test"}

    def test_websocket_not_block_on_close(self, test_client_factory: TestClientFactory) -> None:
        cancelled = False

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            nonlocal cancelled
            try:
                websocket = WebSocket(scope, receive=receive, send=send)
                await websocket.accept()
                await anyio.sleep_forever()
            except anyio.get_cancelled_exc_class():
                cancelled = True
                raise

        client = test_client_factory(app)
        with client.websocket_connect("/"):
            ...
        assert cancelled

    @pytest.mark.parametrize("param", ("2020-07-14T00:00:00+00:00", "España", "voilà"))
    def test_query_params(self, test_client_factory: TestClientFactory, param: str) -> None:
        def homepage(request: Request) -> Response:
            return Response(request.query_params["param"])

        app = Speedy(routes=[Route("/", endpoint=homepage)])
        client = test_client_factory(app)
        response = client.get("/", params={"param": param})
        assert response.text == param

    @pytest.mark.parametrize(
        "domain, ok",
        [
            pytest.param("testserver", True),
            ("testserver.local", True),
            ("localhost", False),
            ("example.com", False),
        ],
    )
    def test_domain_restricted_cookies(self, test_client_factory: TestClientFactory, domain: str, ok: bool) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            response = Response("Hello, world!", media_type="text/plain")
            response.set_cookie(
                "mycookie",
                "myvalue",
                path="/",
                domain=domain,
            )
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        cookie_set = len(response.cookies) == 1
        assert cookie_set == ok

    @pytest.mark.parametrize(
        ("follow_redirects", "expected_status_code"),
        [(True, 200), (False, 307)],
        ids=("follow", "nofollow"),
    )
    def test_forward_redirects(
            self, test_client_factory: TestClientFactory, follow_redirects: bool, expected_status_code: int
    ) -> None:
        client = test_client_factory(redirect_app, follow_redirects=follow_redirects)
        response = client.get("/")
        assert response.status_code == expected_status_code

    def test_with_duplicate_headers(self, test_client_factory: TestClientFactory) -> None:
        def homepage(request: Request) -> JSONResponse:
            return JSONResponse({"x-token": request.headers.getlist("x-token")})

        app = Speedy(routes=[Route("/", endpoint=homepage)])
        client = test_client_factory(app)
        response = client.get("/", headers=[("x-token", "foo"), ("x-token", "bar")])
        assert response.json() == {"x-token": ["foo", "bar"]}

    def test_merge_url(self, test_client_factory: TestClientFactory) -> None:
        def homepage(request: Request) -> Response:
            return Response(request.url.path)

        app = Speedy(routes=[Route("/api/v1/bar", endpoint=homepage)])
        client = test_client_factory(app, base_url="http://testserver/api/v1/")
        response = client.get("/bar")
        assert response.text == "/api/v1/bar"

    def test_raw_path_with_querystring(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            response = Response(scope.get("raw_path"))
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/hello-world", params={"foo": "bar"})
        assert response.content == b"/hello-world"

    @pytest.mark.parametrize(
        ("base_url", "server", "host"),
        [
            ("http://[::1]", ["::1", 80], "[::1]"),
            ("http://[::1]:8000", ["::1", 8000], "[::1]:8000"),
            ("http://[::1]:0", ["::1", 0], "[::1]:0"),
        ],
    )
    def test_ipv6_base_url(
            self, test_client_factory: TestClientFactory, base_url: str, server: list[str | int], host: str
    ) -> None:
        def homepage(request: Request) -> JSONResponse:
            return JSONResponse({"server": request.scope["server"], "host": request.headers["host"]})

        app = Speedy(routes=[Route("/", endpoint=homepage)])
        client = test_client_factory(app, base_url=base_url)
        response = client.get("/")
        assert response.json() == {"server": server, "host": host}

    def test_websocket_raw_path_without_params(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            websocket = WebSocket(scope, receive=receive, send=send)
            await websocket.accept()
            raw_path = scope.get("raw_path")
            assert raw_path is not None
            await websocket.send_bytes(raw_path)

        client = test_client_factory(app)
        with client.websocket_connect("/hello-world", params={"foo": "bar"}) as websocket:
            data = websocket.receive_bytes()
            assert data == b"/hello-world"
