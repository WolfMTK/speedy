
import contextlib
import functools
import json
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Generator
from typing import Any, TypedDict

import pytest
from speedy.application import Speedy
from speedy.exceptions import WebSocketDisconnect, HTTPException
from speedy.middleware import Middleware
from speedy.requests import Request
from speedy.responses import Response, JSONResponse, PlainTextResponse
from speedy.routing import Router, Route, Mount, WebSocketRoute, NoMatchFound, Host
from speedy.testclient import TestClient
from speedy.types import ASGIApplication, Scope, Receive, Send, Message
from speedy.websocket import WebSocket
from typing_extensions import Never

from tests.types import TestClientFactory


def homepage(request: Request) -> Response:
    return Response("Hello, world", media_type="text/plain")


def users(request: Request) -> Response:
    return Response("All users", media_type="text/plain")


def user(request: Request) -> Response:
    content = "User " + request.path_params["username"]
    return Response(content, media_type="text/plain")


def user_me(request: Request) -> Response:
    content = "User fixed me"
    return Response(content, media_type="text/plain")


def disable_user(request: Request) -> Response:
    content = "User " + request.path_params["username"] + " disabled"
    return Response(content, media_type="text/plain")


def user_no_match(request: Request) -> Response:  # pragma: no cover
    content = "User fixed no match"
    return Response(content, media_type="text/plain")


async def partial_endpoint(arg: str, request: Request) -> JSONResponse:
    return JSONResponse({"arg": arg})


async def partial_ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"url": str(websocket.url)})
    await websocket.close()


class PartialRoutes:
    @classmethod
    async def async_endpoint(cls, arg: str, request: Request) -> JSONResponse:
        return JSONResponse({"arg": arg})

    @classmethod
    async def async_ws_endpoint(cls, websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"url": str(websocket.url)})
        await websocket.close()


def func_homepage(request: Request) -> Response:
    return Response("Hello, world!", media_type="text/plain")


def contact(request: Request) -> Response:
    return Response("Hello, POST!", media_type="text/plain")


def search(request: Request) -> Response:
    return Response("Hello, QUERY!", media_type="text/plain")


def int_convertor(request: Request) -> JSONResponse:
    number = request.path_params["param"]
    return JSONResponse({"int": number})


def float_convertor(request: Request) -> JSONResponse:
    num = request.path_params["param"]
    return JSONResponse({"float": num})


def path_convertor(request: Request) -> JSONResponse:
    path = request.path_params["param"]
    return JSONResponse({"path": path})


def uuid_converter(request: Request) -> JSONResponse:
    uuid_param = request.path_params["param"]
    return JSONResponse({"uuid": str(uuid_param)})


def path_with_parentheses(request: Request) -> JSONResponse:
    number = request.path_params["param"]
    return JSONResponse({"int": number})


async def websocket_endpoint(session: WebSocket) -> None:
    await session.accept()
    await session.send_text("Hello, world!")
    await session.close()


async def websocket_params(session: WebSocket) -> None:
    await session.accept()
    await session.send_text(f"Hello, {session.path_params['room']}!")
    await session.close()


app = Router(
    [
        Route("/", endpoint=homepage, methods=["GET"]),
        Mount(
            "/users",
            routes=[
                Route("/", endpoint=users),
                Route("/me", endpoint=user_me),
                Route("/{username}", endpoint=user),
                Route("/{username}:disable", endpoint=disable_user, methods=["PUT"]),
                Route("/nomatch", endpoint=user_no_match),
            ],
        ),
        Mount(
            "/partial",
            routes=[
                Route("/", endpoint=functools.partial(partial_endpoint, "foo")),
                Route(
                    "/cls",
                    endpoint=functools.partial(PartialRoutes.async_endpoint, "foo"),
                ),
                WebSocketRoute("/ws", endpoint=functools.partial(partial_ws_endpoint)),
                WebSocketRoute(
                    "/ws/cls",
                    endpoint=functools.partial(PartialRoutes.async_ws_endpoint),
                ),
            ],
        ),
        Mount("/static", app=Response("xxxxx", media_type="image/png")),
        Route("/func", endpoint=func_homepage, methods=["GET"]),
        Route("/func", endpoint=contact, methods=["POST"]),
        Route("/search", endpoint=search, methods=["QUERY"]),
        Route("/int/{param:int}", endpoint=int_convertor, name="int-convertor"),
        Route("/float/{param:float}", endpoint=float_convertor, name="float-convertor"),
        Route("/path/{param:path}", endpoint=path_convertor, name="path-convertor"),
        Route("/uuid/{param:uuid}", endpoint=uuid_converter, name="uuid-convertor"),
        Route(
            "/path-with-parentheses({param:int})",
            endpoint=path_with_parentheses,
            name="path-with-parentheses",
        ),
        WebSocketRoute("/ws", endpoint=websocket_endpoint),
        WebSocketRoute("/ws/{room}", endpoint=websocket_params),
    ]
)


@pytest.fixture
def client(
        test_client_factory: TestClientFactory,
) -> Generator[TestClient, None, None]:
    with test_client_factory(app) as client:
        yield client


def http_endpoint(request: Request) -> Response:
    url = request.url_for("http_endpoint")
    return Response(f"URL: {url}", media_type="text/plain")


class WebSocketEndpoint:
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        websocket = WebSocket(scope=scope, receive=receive, send=send)
        await websocket.accept()
        await websocket.send_json({"URL": str(websocket.url_for("websocket_endpoint"))})
        await websocket.close()


mixed_protocol_app = Router(
    routes=[
        Route("/", endpoint=http_endpoint),
        WebSocketRoute("/", endpoint=WebSocketEndpoint(), name="websocket_endpoint"),
    ]
)

ok = PlainTextResponse("OK")


def users_api(request: Request) -> JSONResponse:
    return JSONResponse({"users": [{"username": "tom"}]})


mixed_hosts_app = Router(
    routes=[
        Host(
            "www.example.org",
            app=Router(
                [
                    Route("/", homepage, name="homepage"),
                    Route("/users", users, name="users"),
                ]
            ),
        ),
        Host(
            "api.example.org",
            name="api",
            app=Router([Route("/users", users_api, name="users")]),
        ),
        Host(
            "port.example.org:3600",
            name="port",
            app=Router([Route("/", homepage, name="homepage")]),
        ),
    ]
)


async def subdomain_app(scope: Scope, receive: Receive, send: Send) -> None:
    response = JSONResponse({"subdomain": scope["path_params"]["subdomain"]})
    await response(scope, receive, send)


subdomain_router = Router(routes=[Host("{subdomain}.example.org", app=subdomain_app, name="subdomains")])


async def echo_urls(request: Request) -> JSONResponse:
    return JSONResponse(
        {
            "index": str(request.url_for("index")),
            "submount": str(request.url_for("mount:submount")),
        }
    )


echo_url_routes = [
    Route("/", echo_urls, name="index", methods=["GET"]),
    Mount(
        "/submount",
        name="mount",
        routes=[Route("/", echo_urls, name="submount", methods=["GET"])],
    ),
]


async def stub_app(scope: Scope, receive: Receive, send: Send) -> None:
    pass  # pragma: no cover


double_mount_routes = [
    Mount("/mount", name="mount", routes=[Mount("/static", stub_app, name="static")]),
]


async def ws_helloworld(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_text("Hello, world!")
    await websocket.close()


class Endpoint:
    async def my_method(self, request: Request) -> None: ...  # pragma: no cover

    @classmethod
    async def my_classmethod(cls, request: Request) -> None: ...  # pragma: no cover

    @staticmethod
    async def my_staticmethod(request: Request) -> None: ...  # pragma: no cover

    def __call__(self, request: Request) -> None: ...  # pragma: no cover


class AddHeadersMiddleware:
    def __init__(self, app: ASGIApplication) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["add_headers_middleware"] = True

        async def modified_send(msg: Message) -> None:
            if msg["type"] == "http.response.start":
                msg["headers"].append((b"X-Test", b"Set by middleware"))
            await send(msg)

        await self.app(scope, receive, modified_send)


def assert_middleware_header_route(request: Request) -> Response:
    assert request.scope["add_headers_middleware"] is True
    return Response()


route_with_middleware = Speedy(
    routes=[
        Route(
            "/http",
            endpoint=assert_middleware_header_route,
            methods=["GET"],
            middleware=[Middleware(AddHeadersMiddleware)],
        ),
        Route("/home", homepage),
    ]
)

mounted_routes_with_middleware = Speedy(
    routes=[
        Mount(
            "/http",
            routes=[
                Route(
                    "/",
                    endpoint=assert_middleware_header_route,
                    methods=["GET"],
                    name="route",
                ),
            ],
            middleware=[Middleware(AddHeadersMiddleware)],
        ),
        Route("/home", homepage),
    ]
)


mounted_app_with_middleware = Speedy(
    routes=[
        Mount(
            "/http",
            app=Route(
                "/",
                endpoint=assert_middleware_header_route,
                methods=["GET"],
                name="route",
            ),
            middleware=[Middleware(AddHeadersMiddleware)],
        ),
        Route("/home", homepage),
    ]
)


async def echo_paths(request: Request, name: str) -> JSONResponse:
    return JSONResponse(
        {
            "name": name,
            "path": request.scope["path"],
            "root_path": request.scope["root_path"],
        }
    )


async def pure_asgi_echo_paths(scope: Scope, receive: Receive, send: Send, name: str) -> None:
    data = {"name": name, "path": scope["path"], "root_path": scope["root_path"]}
    content = json.dumps(data).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": content})


echo_paths_routes = [
    Route(
        "/path",
        functools.partial(echo_paths, name="path"),
        name="path",
        methods=["GET"],
    ),
    Route(
        "/root-queue/path",
        functools.partial(echo_paths, name="queue_path"),
        name="queue_path",
        methods=["POST"],
    ),
    Mount("/asgipath", app=functools.partial(pure_asgi_echo_paths, name="asgipath")),
    Mount(
        "/sub",
        name="mount",
        routes=[
            Route(
                "/path",
                functools.partial(echo_paths, name="subpath"),
                name="subpath",
                methods=["GET"],
            ),
        ],
    ),
]


class TestBasicRouting:
    def test_router(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert response.text == "Hello, world"

        response = client.post("/")
        assert response.status_code == 405
        assert response.text == "Method Not Allowed"
        assert set(response.headers["allow"].split(", ")) == {"HEAD", "GET"}

        response = client.get("/foo")
        assert response.status_code == 404
        assert response.text == "Not Found"

        response = client.get("/users")
        assert response.status_code == 200
        assert response.text == "All users"

        response = client.get("/users/tomchristie")
        assert response.status_code == 200
        assert response.text == "User tomchristie"

        response = client.get("/users/me")
        assert response.status_code == 200
        assert response.text == "User fixed me"

        response = client.get("/users/tomchristie/")
        assert response.status_code == 200
        assert response.url == "http://testserver/users/tomchristie"
        assert response.text == "User tomchristie"

        response = client.put("/users/tomchristie:disable")
        assert response.status_code == 200
        assert response.url == "http://testserver/users/tomchristie:disable"
        assert response.text == "User tomchristie disabled"

        response = client.get("/users/nomatch")
        assert response.status_code == 200
        assert response.text == "User nomatch"

        response = client.get("/static/123")
        assert response.status_code == 200
        assert response.text == "xxxxx"

    @pytest.mark.parametrize(
        ("method", "expected_text"),
        [("get", "Hello, world!"), ("post", "Hello, POST!")],
        ids=("get", "post"),
    )
    def test_router_methods(self, client: TestClient, method: str, expected_text: str) -> None:
        response = getattr(client, method)("/func")
        assert response.status_code == 200
        assert response.text == expected_text

    def test_router_query_method(self, client: TestClient) -> None:
        response = client.request("QUERY", "/search")
        assert response.status_code == 200
        assert response.text == "Hello, QUERY!"

        response = client.get("/search")
        assert response.status_code == 405
        assert response.text == "Method Not Allowed"
        assert response.headers["allow"] == "QUERY"

    def test_router_add_websocket_route(self, client: TestClient) -> None:
        with client.websocket_connect("/ws") as session:
            text = session.receive_text()
            assert text == "Hello, world!"

        with client.websocket_connect("/ws/test") as session:
            text = session.receive_text()
            assert text == "Hello, test!"

    def test_protocol_switch(self, test_client_factory: TestClientFactory) -> None:
        client = test_client_factory(mixed_protocol_app)

        response = client.get("/")
        assert response.status_code == 200
        assert response.text == "URL: http://testserver/"

        with client.websocket_connect("/") as session:
            assert session.receive_json() == {"URL": "ws://testserver/"}

        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/404"):
                pass  # pragma: no cover

    @pytest.mark.parametrize(
        ("path", "expected_status", "expected_text"),
        [("/", 200, "Hello, World!"), ("/invalid", 404, "Not Found")],
        ids=("match", "no_match"),
    )
    def test_standalone_route(
            self,
            test_client_factory: TestClientFactory,
            path: str,
            expected_status: int,
            expected_text: str,
    ) -> None:
        client = test_client_factory(Route("/", PlainTextResponse("Hello, World!")))
        response = client.get(path)
        assert response.status_code == expected_status
        assert response.text == expected_text

    @pytest.mark.parametrize(
        ("path", "expected_text"),
        [("/", "Hello, world!"), ("/invalid", None)],
        ids=("match", "no_match"),
    )
    def test_standalone_ws_route(
            self,
            test_client_factory: TestClientFactory,
            path: str,
            expected_text: str | None,
    ) -> None:
        client = test_client_factory(WebSocketRoute("/", ws_helloworld))
        if expected_text is None:
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect(path):
                    pass  # pragma: no cover
        else:
            with client.websocket_connect(path) as websocket:
                assert websocket.receive_text() == expected_text


class TestConvertors:
    def test_route_converters(self, client: TestClient) -> None:
        response = client.get("/int/5")
        assert response.status_code == 200
        assert response.json() == {"int": 5}
        assert app.url_path_for("int-convertor", param=5) == "/int/5"

        response = client.get("/path-with-parentheses(7)")
        assert response.status_code == 200
        assert response.json() == {"int": 7}
        assert app.url_path_for("path-with-parentheses", param=7) == "/path-with-parentheses(7)"

        response = client.get("/float/25.5")
        assert response.status_code == 200
        assert response.json() == {"float": 25.5}
        assert app.url_path_for("float-convertor", param=25.5) == "/float/25.5"

        response = client.get("/path/some/example")
        assert response.status_code == 200
        assert response.json() == {"path": "some/example"}
        assert app.url_path_for("path-convertor", param="some/example") == "/path/some/example"

        response = client.get("/uuid/ec38df32-ceda-4cfa-9b4a-1aeb94ad551a")
        assert response.status_code == 200
        assert response.json() == {"uuid": "ec38df32-ceda-4cfa-9b4a-1aeb94ad551a"}
        assert (
                app.url_path_for("uuid-convertor", param=uuid.UUID("ec38df32-ceda-4cfa-9b4a-1aeb94ad551a"))
                == "/uuid/ec38df32-ceda-4cfa-9b4a-1aeb94ad551a"
        )


class TestRouteNames:
    @pytest.mark.parametrize(
        "endpoint, expected_name",
        [
            pytest.param(func_homepage, "func_homepage", id="function"),
            pytest.param(Endpoint().my_method, "my_method", id="method"),
            pytest.param(Endpoint.my_classmethod, "my_classmethod", id="classmethod"),
            pytest.param(
                Endpoint.my_staticmethod,
                "my_staticmethod",
                id="staticmethod",
            ),
            pytest.param(Endpoint(), "Endpoint", id="object"),
            pytest.param(lambda request: ..., "<lambda>", id="lambda"),  # pragma: no branch
        ],
    )
    def test_route_name(self, endpoint: Callable[..., Response], expected_name: str) -> None:
        assert Route(path="/", endpoint=endpoint).name == expected_name

    def test_duplicated_param_names(self) -> None:
        with pytest.raises(
                ValueError,
                match="Duplicated param name id at path /{id}/{id}",
        ):
            Route("/{id}/{id}", user)

        with pytest.raises(
                ValueError,
                match="Duplicated param names id, name at path /{id}/{name}/{id}/{name}",
        ):
            Route("/{id}/{name}/{id}/{name}", user)


class TestURLGeneration:
    def test_url_path_for(self) -> None:
        assert app.url_path_for("homepage") == "/"
        assert app.url_path_for("user", username="tomchristie") == "/users/tomchristie"
        assert app.url_path_for("websocket_endpoint") == "/ws"
        with pytest.raises(NoMatchFound, match='No route exists for name "broken" and params "".'):
            assert app.url_path_for("broken")
        with pytest.raises(NoMatchFound, match='No route exists for name "broken" and params "key, key2".'):
            assert app.url_path_for("broken", key="value", key2="value2")
        with pytest.raises(ValueError):
            app.url_path_for("user", username="tom/christie")
        with pytest.raises(ValueError):
            app.url_path_for("user", username="")

    def test_url_for(self) -> None:
        assert app.url_path_for("homepage").make_absolute_url(base_url="https://example.org") == "https://example.org/"
        assert (
                app.url_path_for("homepage").make_absolute_url(base_url="https://example.org/root_path/")
                == "https://example.org/root_path/"
        )
        assert (
                app.url_path_for("user", username="tomchristie").make_absolute_url(base_url="https://example.org")
                == "https://example.org/users/tomchristie"
        )
        assert (
                app.url_path_for("user", username="tomchristie").make_absolute_url(base_url="https://example.org/root_path/")
                == "https://example.org/root_path/users/tomchristie"
        )
        assert (
                app.url_path_for("websocket_endpoint").make_absolute_url(base_url="https://example.org")
                == "wss://example.org/ws"
        )

    def test_reverse_mount_urls(self) -> None:
        mounted = Router([Mount("/users", ok, name="users")])
        assert mounted.url_path_for("users", path="/a") == "/users/a"

        users = Router([Route("/{username}", ok, name="user")])
        mounted = Router([Mount("/{subpath}/users", users, name="users")])
        assert mounted.url_path_for("users:user", subpath="test", username="tom") == "/test/users/tom"
        assert mounted.url_path_for("users", subpath="test", path="/tom") == "/test/users/tom"

        mounted = Router([Mount("/users", ok, name="users")])
        with pytest.raises(NoMatchFound):
            mounted.url_path_for("users", path="/a", foo="bar")

        mounted = Router([Mount("/users", ok, name="users")])
        with pytest.raises(NoMatchFound):
            mounted.url_path_for("users")

    def test_host_reverse_urls(self) -> None:
        assert mixed_hosts_app.url_path_for("homepage").make_absolute_url("https://whatever") == "https://www.example.org/"
        assert (
                mixed_hosts_app.url_path_for("users").make_absolute_url("https://whatever") == "https://www.example.org/users"
        )
        assert (
                mixed_hosts_app.url_path_for("api:users").make_absolute_url("https://whatever")
                == "https://api.example.org/users"
        )
        assert (
                mixed_hosts_app.url_path_for("port:homepage").make_absolute_url("https://whatever")
                == "https://port.example.org:3600/"
        )
        with pytest.raises(NoMatchFound):
            mixed_hosts_app.url_path_for("api", path="whatever", foo="bar")

    def test_subdomain_reverse_urls(self) -> None:
        assert (
                subdomain_router.url_path_for("subdomains", subdomain="foo", path="/homepage").make_absolute_url(
                    "https://whatever"
                )
                == "https://foo.example.org/homepage"
        )

    def test_url_for_with_double_mount(self) -> None:
        app_under_test = Speedy(routes=double_mount_routes)
        url = app_under_test.url_path_for("mount:static", path="123")
        assert url == "/mount/static/123"

    @pytest.mark.parametrize(
        ("app_under_test", "expected_path"),
        [
            pytest.param(mounted_routes_with_middleware, "/http/", id="routes_with_middleware"),
            pytest.param(mounted_app_with_middleware, None, id="asgi_app_with_middleware"),
        ],
    )
    def test_mount_middleware_url_path_for(
            self, app_under_test: Speedy, expected_path: str | None
    ) -> None:
        if expected_path is None:
            with pytest.raises(NoMatchFound):
                app_under_test.url_path_for("route")
        else:
            assert app_under_test.url_path_for("route") == expected_path


class TestMount:
    def test_mount_urls(self, test_client_factory: TestClientFactory) -> None:
        mounted = Router([Mount("/users", ok, name="users")])
        client = test_client_factory(mounted)
        assert client.get("/users").status_code == 200
        assert client.get("/users").url == "http://testserver/users/"
        assert client.get("/users/").status_code == 200
        assert client.get("/users/a").status_code == 200
        assert client.get("/usersa").status_code == 404

    def test_mount_at_root(self, test_client_factory: TestClientFactory) -> None:
        mounted = Router([Mount("/", ok, name="users")])
        client = test_client_factory(mounted)
        assert client.get("/").status_code == 200

    def test_add_route_to_app_after_mount(self, test_client_factory: TestClientFactory) -> None:
        inner_app = Router()
        app_under_test = Mount("/http", app=inner_app)
        inner_app.add_route(
            "/inner",
            endpoint=homepage,
            methods=["GET"],
        )
        client = test_client_factory(app_under_test)
        response = client.get("/http/inner")
        assert response.status_code == 200

    def test_exception_on_mounted_apps(self, test_client_factory: TestClientFactory) -> None:
        def exc(request: Request) -> None:
            raise Exception("Exc")

        sub_app = Speedy(routes=[Route("/", exc)])
        app_under_test = Speedy(routes=[Mount("/sub", app=sub_app)])

        client = test_client_factory(app_under_test)
        with pytest.raises(Exception) as ctx:
            client.get("/sub/")
        assert str(ctx.value) == "Exc"


class TestHostRouting:
    def test_host_routing(self, test_client_factory: TestClientFactory) -> None:
        client = test_client_factory(mixed_hosts_app, base_url="https://api.example.org/")

        response = client.get("/users")
        assert response.status_code == 200
        assert response.json() == {"users": [{"username": "tom"}]}

        response = client.get("/")
        assert response.status_code == 404

        client = test_client_factory(mixed_hosts_app, base_url="https://www.example.org/")

        response = client.get("/users")
        assert response.status_code == 200
        assert response.text == "All users"

        response = client.get("/")
        assert response.status_code == 200

        client = test_client_factory(mixed_hosts_app, base_url="https://port.example.org:3600/")

        response = client.get("/users")
        assert response.status_code == 404

        response = client.get("/")
        assert response.status_code == 200

        client = test_client_factory(mixed_hosts_app, base_url="https://port.example.org/")

        response = client.get("/")
        assert response.status_code == 200

        client = test_client_factory(mixed_hosts_app, base_url="https://port.example.org:5600/")

        response = client.get("/")
        assert response.status_code == 200

    @pytest.mark.parametrize(
        ("host", "expected_status"),
        [
            ("api.example.org:evil", 404),
            ("[:::]", 404),
            ("api.example.org:000080", 200),
            ("api.example.org:65536", 200),
            ("api.example.org:100000", 200),
        ],
    )
    def test_host_routing_host_header(
            self, test_client_factory: TestClientFactory, host: str, expected_status: int
    ) -> None:
        client = test_client_factory(mixed_hosts_app, base_url="https://api.example.org/")
        response = client.get("/users", headers={"host": host})
        assert response.status_code == expected_status

    def test_host_routing_ip_literals(self, test_client_factory: TestClientFactory) -> None:
        app_under_test = Router(
            routes=[
                Host("[::1]", app=PlainTextResponse("loopback")),
                Host("[2001:db8::1]", app=PlainTextResponse("documentation")),
                Host("[v1.foo]", app=PlainTextResponse("future")),
            ]
        )

        client = test_client_factory(app_under_test, base_url="https://[::1]/")
        response = client.get("/")
        assert response.text == "loopback"

        client = test_client_factory(app_under_test, base_url="https://[2001:db8::1]/")
        response = client.get("/")
        assert response.text == "documentation"

        client = test_client_factory(app_under_test)
        response = client.get("/", headers={"host": "[v1.foo]"})
        assert response.text == "future"

    def test_subdomain_routing(self, test_client_factory: TestClientFactory) -> None:
        client = test_client_factory(subdomain_router, base_url="https://foo.example.org/")

        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"subdomain": "foo"}


class TestLifespan:
    def test_lifespan_state_unsupported(self, test_client_factory: TestClientFactory) -> None:
        @contextlib.asynccontextmanager
        async def lifespan(app: ASGIApplication) -> AsyncGenerator[dict[str, str], None]:
            yield {"foo": "bar"}

        app_under_test = Router(
            lifespan=lifespan,
            routes=[Mount("/", PlainTextResponse("hello, world"))],
        )

        async def no_state_wrapper(scope: Scope, receive: Receive, send: Send) -> None:
            del scope["state"]
            await app_under_test(scope, receive, send)

        with pytest.raises(RuntimeError, match='The server does not support "state" in the lifespan scope'):
            with test_client_factory(no_state_wrapper):
                raise AssertionError("Should not be called")  # pragma: no cover

    def test_lifespan_state_async_cm(self, test_client_factory: TestClientFactory) -> None:
        startup_complete = False
        shutdown_complete = False

        class State(TypedDict):
            count: int
            items: list[int]

        async def hello_world(request: Request) -> Response:
            assert request.state.count == 0
            request.state.count += 1
            request.state.items.append(1)
            return PlainTextResponse("hello, world")

        @contextlib.asynccontextmanager
        async def lifespan(app: Speedy) -> AsyncIterator[State]:
            nonlocal startup_complete, shutdown_complete
            startup_complete = True
            state = State(count=0, items=[])
            yield state
            shutdown_complete = True
            assert state["count"] == 0
            assert state["items"] == [1, 1]

        app_under_test = Router(
            lifespan=lifespan,
            routes=[Route("/", hello_world)],
        )

        assert not startup_complete
        assert not shutdown_complete
        with test_client_factory(app_under_test) as client:
            assert startup_complete
            assert not shutdown_complete
            client.get("/")
            client.get("/")
        assert startup_complete
        assert shutdown_complete

    def test_raise_on_startup(self, test_client_factory: TestClientFactory) -> None:
        @contextlib.asynccontextmanager
        async def lifespan(app: Speedy) -> AsyncIterator[Never]:
            raise RuntimeError()
            yield  # pragma: no cover

        router = Router(lifespan=lifespan)
        startup_failed = False

        async def app_under_test(scope: Scope, receive: Receive, send: Send) -> None:
            async def _send(message: Message) -> None:
                nonlocal startup_failed
                if message["type"] == "lifespan.startup.failed":  # pragma: no branch
                    startup_failed = True
                return await send(message)

            await router(scope, receive, _send)

        with pytest.raises(RuntimeError):
            with test_client_factory(app_under_test):
                pass  # pragma: no cover
        assert startup_failed

    def test_raise_on_shutdown(self, test_client_factory: TestClientFactory) -> None:
        @contextlib.asynccontextmanager
        async def lifespan(app: Speedy) -> AsyncIterator[None]:
            yield
            raise RuntimeError("Shutdown failed")

        app_under_test = Router(lifespan=lifespan)

        with pytest.raises(RuntimeError, match="Shutdown failed"):
            with test_client_factory(app_under_test):
                pass  # pragma: no cover


class TestPartialEndpoints:
    def test_partial_async_endpoint(self, test_client_factory: TestClientFactory) -> None:
        test_client = test_client_factory(app)
        response = test_client.get("/partial")
        assert response.status_code == 200
        assert response.json() == {"arg": "foo"}

        cls_method_response = test_client.get("/partial/cls")
        assert cls_method_response.status_code == 200
        assert cls_method_response.json() == {"arg": "foo"}

    def test_partial_async_ws_endpoint(self, test_client_factory: TestClientFactory) -> None:
        test_client = test_client_factory(app)
        with test_client.websocket_connect("/partial/ws") as websocket:
            data = websocket.receive_json()
            assert data == {"url": "ws://testserver/partial/ws"}

        with test_client.websocket_connect("/partial/ws/cls") as websocket:
            data = websocket.receive_json()
            assert data == {"url": "ws://testserver/partial/ws/cls"}


class TestMiddleware:
    def test_router_middleware(self, test_client_factory: TestClientFactory) -> None:
        class CustomMiddleware:
            def __init__(self, app: ASGIApplication) -> None:
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                response = PlainTextResponse("OK")
                await response(scope, receive, send)

        app_under_test = Router(
            routes=[Route("/", homepage)],
            middleware=[Middleware(CustomMiddleware)],
        )

        client = test_client_factory(app_under_test)
        response = client.get("/")
        assert response.status_code == 200
        assert response.text == "OK"

    @pytest.mark.parametrize(
        "app_under_test",
        [
            mounted_routes_with_middleware,
            mounted_app_with_middleware,
            route_with_middleware,
        ],
    )
    def test_base_route_middleware(
            self,
            test_client_factory: TestClientFactory,
            app_under_test: Speedy,
    ) -> None:
        test_client = test_client_factory(app_under_test)

        response = test_client.get("/home")
        assert response.status_code == 200
        assert "X-Test" not in response.headers

        response = test_client.get("/http")
        assert response.status_code == 200
        assert response.headers["X-Test"] == "Set by middleware"

    def test_mounted_middleware_does_not_catch_exception(
            self,
            test_client_factory: Callable[..., TestClient],
    ) -> None:
        def exc(request: Request) -> Response:
            raise HTTPException(status_code=403, detail="auth")

        class NamedMiddleware:
            def __init__(self, app: ASGIApplication, name: str) -> None:
                self.app = app
                self.name = name

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                async def modified_send(msg: Message) -> None:
                    if msg["type"] == "http.response.start":
                        msg["headers"].append((f"X-{self.name}".encode(), b"true"))
                    await send(msg)

                await self.app(scope, receive, modified_send)

        app_under_test = Speedy(
            routes=[
                Mount(
                    "/mount",
                    routes=[
                        Route("/err", exc),
                        Route("/home", homepage),
                    ],
                    middleware=[Middleware(NamedMiddleware, name="Mounted")],
                ),
                Route("/err", exc),
                Route("/home", homepage),
            ],
            middleware=[Middleware(NamedMiddleware, name="Outer")],
        )

        client = test_client_factory(app_under_test)

        resp = client.get("/home")
        assert resp.status_code == 200, resp.content
        assert "X-Outer" in resp.headers

        resp = client.get("/err")
        assert resp.status_code == 403, resp.content
        assert "X-Outer" in resp.headers

        resp = client.get("/mount/home")
        assert resp.status_code == 200, resp.content
        assert "X-Mounted" in resp.headers

        resp = client.get("/mount/err")
        assert resp.status_code == 403, resp.content
        assert "X-Mounted" in resp.headers

    def test_websocket_route_middleware(
            self,
            test_client_factory: TestClientFactory,
    ) -> None:
        async def ws_endpoint(session: WebSocket) -> None:
            await session.accept()
            await session.send_text("Hello, world!")
            await session.close()

        class WebsocketMiddleware:
            def __init__(self, app: ASGIApplication) -> None:
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                async def modified_send(msg: Message) -> None:
                    if msg["type"] == "websocket.accept":
                        msg["headers"].append((b"X-Test", b"Set by middleware"))
                    await send(msg)

                await self.app(scope, receive, modified_send)

        app_under_test = Speedy(
            routes=[
                WebSocketRoute(
                    "/ws",
                    endpoint=ws_endpoint,
                    middleware=[Middleware(WebsocketMiddleware)],
                )
            ]
        )

        client = test_client_factory(app_under_test)

        with client.websocket_connect("/ws") as websocket:
            text = websocket.receive_text()
            assert text == "Hello, world!"
            assert websocket.extra_headers == [(b"X-Test", b"Set by middleware")]


class TestRepr:
    @pytest.mark.parametrize(
        ("endpoint", "methods", "expected"),
        [
            pytest.param(homepage, ["GET"], "Route(path='/welcome', name='homepage', methods=['GET', 'HEAD'])", id="with_methods"),
            pytest.param(Endpoint, None, "Route(path='/welcome', name='Endpoint', methods=[])", id="without_methods"),
        ],
    )
    def test_route_repr(self, endpoint: Callable[..., Any], methods: list[str] | None, expected: str) -> None:
        route = Route("/welcome", endpoint=endpoint, methods=methods)
        assert repr(route) == expected

    def test_websocket_route_repr(self) -> None:
        route = WebSocketRoute("/ws", endpoint=websocket_endpoint)
        assert repr(route) == "WebSocketRoute(path='/ws', name='websocket_endpoint')"

    @pytest.mark.parametrize(
        ("name", "expected_prefix"),
        [("", "Mount(path='/app', name='', app="), ("app", "Mount(path='/app', name='app', app=")],
        ids=("unnamed", "named"),
    )
    def test_mount_repr(self, name: str, expected_prefix: str) -> None:
        route = Mount("/app", name=name or None, routes=[Route("/", endpoint=homepage)])
        assert repr(route).startswith(expected_prefix)

    @pytest.mark.parametrize(
        ("name", "expected_prefix"),
        [("", "Host(host='example.com', name='', app="), ("app", "Host(host='example.com', name='app', app=")],
        ids=("unnamed", "named"),
    )
    def test_host_repr(self, name: str, expected_prefix: str) -> None:
        route = Host("example.com", name=name or None, app=Router([Route("/", endpoint=homepage)]))
        assert repr(route).startswith(expected_prefix)


class TestRootPath:
    def test_url_for_with_root_path(self, test_client_factory: TestClientFactory) -> None:
        app_under_test = Speedy(routes=echo_url_routes)
        client = test_client_factory(app_under_test, base_url="https://www.example.org/", root_path="/sub_path")
        response = client.get("/sub_path/")
        assert response.json() == {
            "index": "https://www.example.org/sub_path/",
            "submount": "https://www.example.org/sub_path/submount/",
        }
        response = client.get("/sub_path/submount/")
        assert response.json() == {
            "index": "https://www.example.org/sub_path/",
            "submount": "https://www.example.org/sub_path/submount/",
        }

    def test_url_for_with_root_path_ending_with_slash(self, test_client_factory: TestClientFactory) -> None:
        def homepage_url(request: Request) -> JSONResponse:
            return JSONResponse({"index": str(request.url_for("homepage"))})

        app_under_test = Speedy(routes=[Route("/", homepage_url, name="homepage")])
        client = test_client_factory(app_under_test, base_url="https://www.example.org/", root_path="/sub_path/")
        response = client.get("/sub_path/")
        assert response.json() == {"index": "https://www.example.org/sub_path/"}

    def test_paths_with_root_path(self, test_client_factory: TestClientFactory) -> None:
        app_under_test = Speedy(routes=echo_paths_routes)
        client = test_client_factory(app_under_test, base_url="https://www.example.org/", root_path="/root")
        response = client.get("/root/path")
        assert response.status_code == 200
        assert response.json() == {
            "name": "path",
            "path": "/root/path",
            "root_path": "/root",
        }
        response = client.get("/root/asgipath/")
        assert response.status_code == 200
        assert response.json() == {
            "name": "asgipath",
            "path": "/root/asgipath/",
            "root_path": "/root/asgipath",
        }

        response = client.get("/root/sub/path")
        assert response.status_code == 200
        assert response.json() == {
            "name": "subpath",
            "path": "/root/sub/path",
            "root_path": "/root/sub",
        }

        response = client.post("/root/root-queue/path")
        assert response.status_code == 200
        assert response.json() == {
            "name": "queue_path",
            "path": "/root/root-queue/path",
            "root_path": "/root",
        }