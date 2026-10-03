from collections.abc import AsyncGenerator, AsyncIterator, Callable, Generator
from contextlib import asynccontextmanager
from typing import TypedDict

import anyio.from_thread
import pytest
from speedy import status
from speedy.application import Speedy
from speedy.exceptions import HTTPException, WebSocketException
from speedy.requests import Request
from speedy.responses import JSONResponse, PlainTextResponse
from speedy.routing import Host, Mount, Route, Router, WebSocketRoute
from speedy.testclient import TestClient, WebSocketDenialResponse
from speedy.types import ASGIApplication, Receive, Scope, Send
from speedy.websocket import WebSocket
from tests.types import TestClientFactory


class CustomState(TypedDict):
    count: int


async def error_500(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"detail": "Server Error"}, status_code=500)


async def method_not_allowed(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"detail": "Custom message"}, status_code=405)


async def http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


def func_homepage(request: Request) -> PlainTextResponse:
    return PlainTextResponse("Hello, world!")


async def async_homepage(request: Request) -> PlainTextResponse:
    return PlainTextResponse("Hello, world!")


def all_users_page(request: Request) -> PlainTextResponse:
    return PlainTextResponse("Hello, everyone!")


def user_page(request: Request) -> PlainTextResponse:
    username = request.path_params["username"]
    return PlainTextResponse(f"Hello, {username}!")


def custom_subdomain(request: Request) -> PlainTextResponse:
    return PlainTextResponse("Subdomain: " + request.path_params["subdomain"])


def runtime_error(request: Request) -> None:
    raise RuntimeError()


async def websocket_endpoint(session: WebSocket) -> None:
    await session.accept()
    await session.send_text("Hello, world!")
    await session.close()


async def websocket_raise_websocket_exception(websocket: WebSocket) -> None:
    await websocket.accept()
    raise WebSocketException(code=status.WS_1003_UNSUPPORTED_DATA)


async def websocket_raise_http_exception(websocket: WebSocket) -> None:
    raise HTTPException(status_code=401, detail="Unauthorized")


class CustomWSException(Exception):
    pass


async def websocket_raise_custom(websocket: WebSocket) -> None:
    await websocket.accept()
    raise CustomWSException()


async def websocket_state(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"count": websocket.state["count"]})
    await websocket.close()


def custom_ws_exception_handler(websocket: WebSocket, exc: CustomWSException) -> None:
    anyio.from_thread.run(websocket.close, status.WS_1013_TRY_AGAIN_LATER)


@asynccontextmanager
async def lifespan(app: Speedy) -> AsyncGenerator[CustomState]:
    yield {"count": 1}


async def state_count(request: Request) -> JSONResponse:
    return JSONResponse({"count": request.state["count"]}, status_code=200)


users = Router(
    routes=[
        Route("/", endpoint=all_users_page),
        Route("/{username}", endpoint=user_page),
    ]
)

subdomain = Router(
    routes=[
        Route("/", custom_subdomain),
    ]
)

exception_handlers = {
    500: error_500,
    405: method_not_allowed,
    HTTPException: http_exception,
    CustomWSException: custom_ws_exception_handler,
}

app = Speedy(
    routes=[
        Route("/func", endpoint=func_homepage),
        Route("/async", endpoint=async_homepage),
        Route("/state", endpoint=state_count),
        Route("/500", endpoint=runtime_error),
        WebSocketRoute("/ws", endpoint=websocket_endpoint),
        WebSocketRoute("/ws-raise-websocket", endpoint=websocket_raise_websocket_exception),
        WebSocketRoute("/ws-raise-http", endpoint=websocket_raise_http_exception),
        WebSocketRoute("/ws-raise-custom", endpoint=websocket_raise_custom),
        WebSocketRoute("/ws-state", endpoint=websocket_state),
        Mount("/users", app=users),
        Host("{subdomain}.example.org", app=subdomain),
    ],
    exception_handlers=exception_handlers,
    lifespan=lifespan,
)


@pytest.fixture
def client(test_client_factory: TestClientFactory) -> Generator[TestClient, None, None]:
    with test_client_factory(app) as client:
        yield client


class TestRoutes:
    def test_url_path_for(self) -> None:
        assert app.url_path_for("func_homepage") == "/func"

    def test_func_route(self, client: TestClient) -> None:
        response = client.get("/func")
        assert response.status_code == 200
        assert response.text == "Hello, world!"

        response = client.head("/func")
        assert response.status_code == 200
        assert response.text == ""

    def test_async_route(self, client: TestClient) -> None:
        response = client.get("/async")
        assert response.status_code == 200
        assert response.text == "Hello, world!"

    def test_mounted_route(self, client: TestClient) -> None:
        response = client.get("/users/")
        assert response.status_code == 200
        assert response.text == "Hello, everyone!"

    def test_mounted_route_path_params(self, client: TestClient) -> None:
        response = client.get("/users/tomchristie")
        assert response.status_code == 200
        assert response.text == "Hello, tomchristie!"

    def test_subdomain_route(self, test_client_factory: TestClientFactory) -> None:
        client = test_client_factory(app, base_url="https://foo.example.org/")

        response = client.get("/")
        assert response.status_code == 200
        assert response.text == "Subdomain: foo"

    def test_routes(self) -> None:
        assert app.routes == [
            Route("/func", endpoint=func_homepage, methods=["GET"]),
            Route("/async", endpoint=async_homepage, methods=["GET"]),
            Route("/state", endpoint=state_count, methods=["GET"]),
            Route("/500", endpoint=runtime_error, methods=["GET"]),
            WebSocketRoute("/ws", endpoint=websocket_endpoint),
            WebSocketRoute("/ws-raise-websocket", endpoint=websocket_raise_websocket_exception),
            WebSocketRoute("/ws-raise-http", endpoint=websocket_raise_http_exception),
            WebSocketRoute("/ws-raise-custom", endpoint=websocket_raise_custom),
            WebSocketRoute("/ws-state", endpoint=websocket_state),
            Mount(
                "/users",
                app=Router(
                    routes=[
                        Route("/", endpoint=all_users_page),
                        Route("/{username}", endpoint=user_page),
                    ]
                ),
            ),
            Host(
                "{subdomain}.example.org",
                app=Router(routes=[Route("/", endpoint=custom_subdomain)]),
            ),
        ]

    def test_add_route(self, test_client_factory: TestClientFactory) -> None:
        async def homepage(request: Request) -> PlainTextResponse:
            return PlainTextResponse("Hello, World!")

        app = Speedy(
            routes=[
                Route("/", endpoint=homepage),
            ]
        )

        client = test_client_factory(app)
        response = client.get("/")
        assert response.status_code == 200
        assert response.text == "Hello, World!"


class TestWebSocketRoutes:
    def test_websocket_route(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as session:
            text = session.receive_text()
            assert text == "Hello, world!"

    def test_add_websocket_route(self, test_client_factory: TestClientFactory) -> None:
        async def websocket_endpoint(session: WebSocket) -> None:
            await session.accept()
            await session.send_text("Hello, world!")
            await session.close()

        app = Speedy(
            routes=[
                WebSocketRoute("/ws", endpoint=websocket_endpoint),
            ]
        )
        client = test_client_factory(app)

        with client.websocket_connect("/ws") as session:
            text = session.receive_text()
            assert text == "Hello, world!"

    def test_raise_websocket_exception(self, client: TestClient) -> None:
        with client.websocket_connect("/ws-raise-websocket") as session:
            response = session.receive()
            assert response == {
                "type": "websocket.close",
                "code": status.WS_1003_UNSUPPORTED_DATA,
                "reason": "",
            }

    def test_raise_http_exception(self, client: TestClient) -> None:
        with pytest.raises(WebSocketDenialResponse) as exc:
            with client.websocket_connect("/ws-raise-http"):
                pass
        assert exc.value.status_code == 401
        assert exc.value.content == b'{"detail":"Unauthorized"}'

    def test_raise_custom_exception(self, client: TestClient) -> None:
        with client.websocket_connect("/ws-raise-custom") as session:
            response = session.receive()
            assert response == {
                "type": "websocket.close",
                "code": status.WS_1013_TRY_AGAIN_LATER,
                "reason": "",
            }


class TestExceptionHandlers:
    def test_404(self, client: TestClient) -> None:
        response = client.get("/404")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}

    def test_405(self, client: TestClient) -> None:
        response = client.post("/func")
        assert response.status_code == 405
        assert response.json() == {"detail": "Custom message"}

    def test_500(self, test_client_factory: TestClientFactory) -> None:
        client = test_client_factory(app, raise_server_exceptions=False)
        response = client.get("/500")
        assert response.status_code == 500
        assert response.json() == {"detail": "Server Error"}


class TestState:
    def test_request_state(self, client: TestClient) -> None:
        response = client.get("/state")
        assert response.status_code == 200
        assert response.json() == {"count": 1}

    def test_websocket_state(self, client: TestClient) -> None:
        with client.websocket_connect("/ws-state") as session:
            response = session.receive_json()
            assert response == {"count": 1}


class TestLifespan:
    def test_async_context_manager(self, test_client_factory: TestClientFactory) -> None:
        startup_complete = False
        cleanup_complete = False

        @asynccontextmanager
        async def lifespan(app: ASGIApplication) -> AsyncGenerator[None, None]:
            nonlocal startup_complete, cleanup_complete
            startup_complete = True
            yield
            cleanup_complete = True

        app = Speedy(lifespan=lifespan)

        assert not startup_complete
        assert not cleanup_complete
        with test_client_factory(app):
            assert startup_complete
            assert not cleanup_complete
        assert startup_complete
        assert cleanup_complete

    def test_app_subclass(self) -> None:
        class App(Speedy):
            pass

        @asynccontextmanager
        async def lifespan(app: App) -> AsyncIterator[None]:
            yield

        App(lifespan=lifespan)


class TestMiddleware:
    def test_stack_init(self, test_client_factory: TestClientFactory) -> None:
        class NoOpMiddleware:
            def __init__(self, app: ASGIApplication):
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                await self.app(scope, receive, send)

        class SimpleInitializableMiddleware:
            counter = 0

            def __init__(self, app: ASGIApplication):
                self.app = app
                SimpleInitializableMiddleware.counter += 1

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                await self.app(scope, receive, send)

        def get_app() -> ASGIApplication:
            app = Speedy()
            app.add_middleware(SimpleInitializableMiddleware)
            app.add_middleware(NoOpMiddleware)
            return app

        app = get_app()

        with test_client_factory(app):
            pass

        assert SimpleInitializableMiddleware.counter == 1

        test_client_factory(app).get("/foo")

        assert SimpleInitializableMiddleware.counter == 1

        app = get_app()

        test_client_factory(app).get("/foo")

        assert SimpleInitializableMiddleware.counter == 2

    def test_args(self, test_client_factory: TestClientFactory) -> None:
        calls: list[str] = []

        class MiddlewareWithArgs:
            def __init__(self, app: ASGIApplication, arg: str) -> None:
                self.app = app
                self.arg = arg

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                calls.append(self.arg)
                await self.app(scope, receive, send)

        app = Speedy()
        app.add_middleware(MiddlewareWithArgs, "foo")
        app.add_middleware(MiddlewareWithArgs, "bar")

        with test_client_factory(app):
            pass

        assert calls == ["bar", "foo"]

    def test_factory(self, test_client_factory: TestClientFactory) -> None:
        calls: list[str] = []

        def _middleware_factory(app: ASGIApplication, arg: str) -> ASGIApplication:
            async def _app(scope: Scope, receive: Receive, send: Send) -> None:
                calls.append(arg)
                await app(scope, receive, send)

            return _app

        def get_middleware_factory() -> Callable[[ASGIApplication, str], ASGIApplication]:
            return _middleware_factory

        app = Speedy()
        app.add_middleware(_middleware_factory, arg="foo")
        app.add_middleware(get_middleware_factory(), "bar")

        with test_client_factory(app):
            pass

        assert calls == ["bar", "foo"]


class TestDebugMode:
    def test_debug(self, test_client_factory: TestClientFactory) -> None:
        async def homepage(request: Request) -> None:
            raise RuntimeError()

        app = Speedy(
            routes=[
                Route("/", homepage),
            ],
        )
        app.debug = True

        client = test_client_factory(app, raise_server_exceptions=False)
        response = client.get("/")
        assert response.status_code == 500
        assert "RuntimeError" in response.text
        assert app.debug
