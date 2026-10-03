import sys
from collections.abc import Iterator
from typing import Any

import anyio
import pytest

from speedy.application import Speedy
from speedy.datastructures import URL, Address, State
from speedy.middleware import Middleware
from speedy.requests import ClientDisconnect, Request
from speedy.responses import JSONResponse, PlainTextResponse, Response
from speedy.routing import Route
from speedy.types import ASGIApplication, Message, Receive, Scope, Send
from tests.types import TestClientFactory


class TestRequestAttributes:
    def test_url(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            data = {"method": request.method, "url": str(request.url)}
            response = JSONResponse(data)
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/123?a=abc")
        assert response.json() == {"method": "GET", "url": "http://testserver/123?a=abc"}

        response = client.get("https://example.org:123/")
        assert response.json() == {"method": "GET", "url": "https://example.org:123/"}

    @pytest.mark.parametrize(
        "server",
        [pytest.param(("example.org", 8000), id="tuple"), pytest.param(["example.org", 8000], id="list")],
    )
    def test_url_from_server_without_host_header(self, server: Any) -> None:
        request = Request({"type": "http", "scheme": "http", "path": "/", "headers": [], "server": server})
        assert str(request.url) == "http://example.org:8000/"

    def test_query_params(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            params = dict(request.query_params)
            response = JSONResponse({"params": params})
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/?a=123&b=456")
        assert response.json() == {"params": {"a": "123", "b": "456"}}

    @pytest.mark.skipif(
        any(module in sys.modules for module in ("brotli", "brotlicffi")),
        reason='urllib3 includes "br" to the "accept-encoding" headers.',
    )
    def test_headers(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            headers = dict(request.headers)
            response = JSONResponse({"headers": headers})
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/", headers={"host": "example.org"})
        assert response.json() == {
            "headers": {
                "host": "example.org",
                "user-agent": "testclient",
                "accept-encoding": "gzip, deflate, zstd",
                "accept": "*/*",
                "connection": "keep-alive",
            }
        }

    @pytest.mark.parametrize(
        ("scope", "expected_client"),
        [
            pytest.param({"client": ["client", 42]}, Address("client", 42), id="list"),
            pytest.param({"client": ("client", 42)}, Address("client", 42), id="tuple"),
            pytest.param({"client": None}, None, id="none"),
            pytest.param({}, None, id="missing"),
        ],
    )
    def test_client(self, scope: Scope, expected_client: Address | None) -> None:
        client = Request({**scope, "type": "http"}).client
        assert client == expected_client

    def test_scope_interface(self) -> None:
        request = Request({"type": "http", "method": "GET", "path": "/abc/"})
        assert request["method"] == "GET"
        assert dict(request) == {"type": "http", "method": "GET", "path": "/abc/"}
        assert len(request) == 3

    def test_raw_path(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            path = request.scope["path"]
            raw_path = request.scope["raw_path"]
            response = PlainTextResponse(f"{path}, {raw_path}")
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/he%2Fllo")
        assert response.text == "/he/llo, b'/he%2Fllo'"


class TestRequestState:
    def test_state_object(self) -> None:
        scope = {"state": {"old": "foo"}}

        s = State(scope["state"])

        s.new = "value"
        assert s.new == "value"

        del s.new

        with pytest.raises(AttributeError):
            s.new

        s["dict_key"] = "dict_value"
        assert s["dict_key"] == "dict_value"
        assert s.dict_key == "dict_value"

        s["another_key"] = "another_value"
        keys = list(s)
        assert "old" in keys
        assert "dict_key" in keys
        assert "another_key" in keys

        assert len(s) == 3

        del s["dict_key"]
        assert len(s) == 2
        with pytest.raises(KeyError):
            s["dict_key"]

    def test_request_state(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            request.state.example = 123
            response = JSONResponse({"state.example": request.state.example})
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/123?a=abc")
        assert response.json() == {"state.example": 123}


class TestRequestBody:
    def test_body(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            body = await request.body()
            response = JSONResponse({"body": body.decode()})
            await response(scope, receive, send)

        client = test_client_factory(app)

        response = client.get("/")
        assert response.json() == {"body": ""}

        response = client.post("/", json={"a": "123"})
        assert response.json() == {"body": '{"a":"123"}'}

        response = client.post("/", content="abc")
        assert response.json() == {"body": "abc"}

    def test_stream(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            body = b""
            async for chunk in request.stream():
                body += chunk
            response = JSONResponse({"body": body.decode()})
            await response(scope, receive, send)

        client = test_client_factory(app)

        response = client.get("/")
        assert response.json() == {"body": ""}

        response = client.post("/", json={"a": "123"})
        assert response.json() == {"body": '{"a":"123"}'}

        response = client.post("/", content="abc")
        assert response.json() == {"body": "abc"}

    def test_body_then_stream(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            body = await request.body()
            chunks = b""
            async for chunk in request.stream():
                chunks += chunk
            response = JSONResponse({"body": body.decode(), "stream": chunks.decode()})
            await response(scope, receive, send)

        client = test_client_factory(app)

        response = client.post("/", content="abc")
        assert response.json() == {"body": "abc", "stream": "abc"}

    def test_stream_then_body(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            chunks = b""
            async for chunk in request.stream():
                chunks += chunk
            try:
                body = await request.body()
            except RuntimeError:
                body = b"<stream consumed>"
            response = JSONResponse({"body": body.decode(), "stream": chunks.decode()})
            await response(scope, receive, send)

        client = test_client_factory(app)

        response = client.post("/", content="abc")
        assert response.json() == {"body": "<stream consumed>", "stream": "abc"}

    def test_json(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            data = await request.json()
            response = JSONResponse({"json": data})
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.post("/", json={"a": "123"})
        assert response.json() == {"json": {"a": "123"}}

    def test_chunked_encoding(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            body = await request.body()
            response = JSONResponse({"body": body.decode()})
            await response(scope, receive, send)

        client = test_client_factory(app)

        def post_body() -> Iterator[bytes]:
            yield b"foo"
            yield b"bar"

        response = client.post("/", content=post_body())
        assert response.json() == {"body": "foobar"}

    def test_without_setting_receive(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope)
            try:
                data = await request.json()
            except RuntimeError:
                data = "Receive channel not available"
            response = JSONResponse({"json": data})
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.post("/", json={"a": "123"})
        assert response.json() == {"json": "Receive channel not available"}

    @pytest.mark.parametrize(
        "messages",
        [
            pytest.param([{"body": b"123", "more_body": True}, {"body": b""}], id="data_then_empty"),
            pytest.param([{"body": b"", "more_body": True}, {"body": b"123"}], id="empty_then_data"),
            pytest.param([{"body": b"12", "more_body": True}, {"body": b"3"}], id="data_split_in_two"),
            pytest.param(
                [
                    {"body": b"123", "more_body": True},
                    {"body": b"", "more_body": True},
                    {"body": b""},
                ],
                id="data_then_two_empty",
            ),
        ],
    )
    @pytest.mark.anyio
    async def test_receive_messages(self, messages: list[Message]) -> None:
        messages = messages.copy()

        async def rcv() -> Message:
            return {"type": "http.request", **messages.pop(0)}

        request = Request({"type": "http"}, rcv)

        body = await request.body()

        assert body == b"123"

    @pytest.mark.anyio
    async def test_stream_called_twice(self) -> None:
        messages: list[Message] = [
            {"type": "http.request", "body": b"1", "more_body": True},
            {"type": "http.request", "body": b"2", "more_body": True},
            {"type": "http.request", "body": b"3"},
        ]

        async def rcv() -> Message:
            return messages.pop(0)

        request = Request({"type": "http"}, rcv)

        s1 = request.stream()
        s2 = request.stream()

        msg = await s1.__anext__()
        assert msg == b"1"

        msg = await s2.__anext__()
        assert msg == b"2"

        msg = await s1.__anext__()
        assert msg == b"3"

        msg = await s1.__anext__()
        assert msg == b""
        msg = await s2.__anext__()
        assert msg == b""

        with pytest.raises(StopAsyncIteration):
            assert await s2.__anext__()
        with pytest.raises(StopAsyncIteration):
            await s1.__anext__()


class TestRequestForm:
    def test_form_urlencoded(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            form = await request.form()
            response = JSONResponse({"form": dict(form)})
            await response(scope, receive, send)

        client = test_client_factory(app)

        response = client.post("/", data={"abc": "123 @"})
        assert response.json() == {"form": {"abc": "123 @"}}

    def test_form_context_manager(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            async with request.form() as form:
                response = JSONResponse({"form": dict(form)})
                await response(scope, receive, send)

        client = test_client_factory(app)

        response = client.post("/", data={"abc": "123 @"})
        assert response.json() == {"form": {"abc": "123 @"}}


class TestRequestDisconnect:
    def test_disconnect_while_reading_body(
            self,
            anyio_backend_name: str,
            anyio_backend_options: dict[str, Any],
    ) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            await request.body()

        async def receiver() -> Message:
            return {"type": "http.disconnect"}

        scope = {"type": "http", "method": "POST", "path": "/"}
        with pytest.raises(ClientDisconnect):
            anyio.run(
                app,
                scope,
                receiver,
                None,
                backend=anyio_backend_name,
                backend_options=anyio_backend_options,
            )

    def test_is_disconnected(self, test_client_factory: TestClientFactory) -> None:
        disconnected_after_response = None

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            nonlocal disconnected_after_response

            request = Request(scope, receive)
            body = await request.body()
            disconnected = await request.is_disconnected()
            response = JSONResponse({"body": body.decode(), "disconnected": disconnected})
            await response(scope, receive, send)
            disconnected_after_response = await request.is_disconnected()

        client = test_client_factory(app)
        response = client.post("/", content="foo")
        assert response.json() == {"body": "foo", "disconnected": False}
        assert disconnected_after_response


class TestRequestCookies:
    def test_cookies(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            mycookie = request.cookies.get("mycookie")
            if mycookie:
                response = Response(mycookie, media_type="text/plain")
            else:
                response = Response("Hello, world!", media_type="text/plain")
                response.set_cookie("mycookie", "Hello, cookies!")

            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.text == "Hello, world!"
        response = client.get("/")
        assert response.text == "Hello, cookies!"

    def test_lenient_parsing(self, test_client_factory: TestClientFactory) -> None:
        tough_cookie = (
            "provider-oauth-nonce=validAsciiblabla; "
            'okta-oauth-redirect-params={"responseType":"code","state":"somestate",'
            '"nonce":"somenonce","scopes":["openid","profile","email","phone"],'
            '"urls":{"issuer":"https://subdomain.okta.com/oauth2/authServer",'
            '"authorizeUrl":"https://subdomain.okta.com/oauth2/authServer/v1/authorize",'
            '"userinfoUrl":"https://subdomain.okta.com/oauth2/authServer/v1/userinfo"}}; '
            "importantCookie=importantValue; sessionCookie=importantSessionValue"
        )
        expected_keys = {
            "importantCookie",
            "okta-oauth-redirect-params",
            "provider-oauth-nonce",
            "sessionCookie",
        }

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            response = JSONResponse({"cookies": request.cookies})
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/", headers={"cookie": tough_cookie})
        result = response.json()
        assert len(result["cookies"]) == 4
        assert set(result["cookies"].keys()) == expected_keys

    @pytest.mark.parametrize(
        ("cookie_header", "expected"),
        [
            pytest.param("chips=ahoy; vienna=finger", {"chips": "ahoy", "vienna": "finger"}, id="simple"),
            pytest.param(
                'keebler="E=mc2; L=\\"Loves\\"; fudge=\\012;"',
                {"keebler": '"E=mc2', "L": '\\"Loves\\"', "fudge": "\\012", "": '"'},
                id="semicolons_split_even_inside_quotes",
            ),
            pytest.param("keebler=E=mc2", {"keebler": "E=mc2"}, id="equals_in_unquoted_value"),
            pytest.param("key:term=value:term", {"key:term": "value:term"}, id="colon_in_name"),
            pytest.param("a=b; c=[; d=r; f=h", {"a": "b", "c": "[", "d": "r", "f": "h"}, id="square_bracket"),
            pytest.param("a=b; Domain=example.com", {"a": "b", "Domain": "example.com"}, id="attribute_like_name"),
            pytest.param("a=b; h=i; a=c", {"a": "c", "h": "i"}, id="duplicate_name_keeps_last"),
        ],
    )
    def test_edge_cases(
            self,
            cookie_header: str,
            expected: dict[str, str],
            test_client_factory: TestClientFactory,
    ) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            response = JSONResponse({"cookies": request.cookies})
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/", headers={"cookie": cookie_header})
        result = response.json()
        assert result["cookies"] == expected

    @pytest.mark.parametrize(
        ("cookie_header", "expected"),
        [
            pytest.param(
                "abc=def; unnamed; django_language=en",
                {"": "unnamed", "abc": "def", "django_language": "en"},
                id="chunk_without_equals_is_unnamed_value",
            ),
            pytest.param('a=b; "; c=d', {"a": "b", "": '"', "c": "d"}, id="double_quote_is_unnamed_value"),
            pytest.param("a b c=d e = f; gh=i", {"a b c": "d e = f", "gh": "i"}, id="spaces_and_equals_in_value"),
            pytest.param(
                'a   b,c<>@:/[]?{}=d  "  =e,f g',
                {"a   b,c<>@:/[]?{}": 'd  "  =e,f g'},
                id="characters_forbidden_by_spec",
            ),
            pytest.param(
                "  =  b  ;  ;  =  ;   c  =  ;  ",
                {"": "b", "c": ""},
                id="extra_whitespace_and_semicolons",
            ),
        ],
    )
    def test_invalid(
            self,
            cookie_header: str,
            expected: dict[str, str],
            test_client_factory: TestClientFactory,
    ) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            response = JSONResponse({"cookies": request.cookies})
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/", headers={"cookie": cookie_header})
        result = response.json()
        assert result["cookies"] == expected

    def test_multiple_cookie_headers(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            scope["headers"] = [(b"cookie", b"a=abc"), (b"cookie", b"b=def"), (b"cookie", b"c=ghi")]
            request = Request(scope, receive)
            response = JSONResponse({"cookies": request.cookies})
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        result = response.json()
        assert result["cookies"] == {"a": "abc", "b": "def", "c": "ghi"}


class TestRequestPushPromise:
    def test_send_push_promise(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            scope["extensions"]["http.response.push"] = {}

            request = Request(scope, receive, send)
            await request.send_push_promise("/style.css")

            response = JSONResponse({"json": "OK"})
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.json() == {"json": "OK"}

    def test_without_push_extension(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope)
            await request.send_push_promise("/style.css")

            response = JSONResponse({"json": "OK"})
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.json() == {"json": "OK"}

    def test_without_setting_send(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            scope["extensions"]["http.response.push"] = {}

            data = "OK"
            request = Request(scope)
            try:
                await request.send_push_promise("/style.css")
            except RuntimeError:
                data = "Send channel not available"
            response = JSONResponse({"json": data})
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.json() == {"json": "Send channel not available"}


class TestRequestUrlFor:
    def test_outside_application_context(self, test_client_factory: TestClientFactory) -> None:
        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            request = Request(scope, receive)
            request.url_for("index")

        client = test_client_factory(app)
        with pytest.raises(
                RuntimeError,
                match="The `url_for` method can only be used inside a Speedy application or with a router.",
        ):
            client.get("/")

    def test_inside_application_context(self, test_client_factory: TestClientFactory) -> None:
        url_for = None

        async def homepage(request: Request) -> Response:
            return PlainTextResponse("Hello, world!")

        class CustomMiddleware:
            def __init__(self, app: ASGIApplication) -> None:
                self.app = app

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                nonlocal url_for
                request = Request(scope, receive)
                url_for = request.url_for("homepage")
                await self.app(scope, receive, send)

        app = Speedy(routes=[Route("/home", homepage)], middleware=[Middleware(CustomMiddleware)])

        client = test_client_factory(app)
        client.get("/home")
        assert url_for == URL("http://testserver/home")
