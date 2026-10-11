import asyncio
import contextlib
import functools
import inspect
import json
import mimetypes
import os
import sys
import threading
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Generator,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
    Sequence,
)
from concurrent.futures import Future
from contextlib import AbstractContextManager
from http import HTTPStatus
from http.client import HTTPMessage
from http.cookiejar import Cookie, CookieJar
from typing import Any, Literal, Self, cast
from urllib.parse import unquote, urlencode, urljoin, urlsplit
from urllib.request import Request as UrllibRequest

import zapros
from pywhatwgurl import URL

from speedy.exceptions import WebSocketDisconnect
from speedy.types import Message, Receive, Scope, Send

ASGI3App = Callable[[Scope, Receive, Send], Awaitable[None]]

_RequestData = Mapping[str, str | Iterable[str] | bytes]

_DEFAULT_PORTS = {"http": 80, "ws": 80, "https": 443, "wss": 443}


class _BlockingPortal:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            name="testclient-event-loop",
            daemon=True,
        )

    def __enter__(self) -> Self:
        self._thread.start()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        try:
            self.call(self._cancel_remaining_tasks)
            self.call(self._loop.shutdown_asyncgens)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join()
            self._loop.close()

    async def _cancel_remaining_tasks(self) -> None:
        current = asyncio.current_task()
        tasks = [task for task in asyncio.all_tasks() if task is not current]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _invoke[T](self, func: Callable[..., T | Awaitable[T]], *args: Any) -> T:
        result = func(*args)
        if inspect.isawaitable(result):
            return await result
        return cast(T, result)

    def start_task_soon[T](self, func: Callable[..., T | Awaitable[T]], *args: Any) -> Future[T]:
        return asyncio.run_coroutine_threadsafe(self._invoke(func, *args), self._loop)

    def call[T](self, func: Callable[..., T | Awaitable[T]], *args: Any) -> T:
        return self.start_task_soon(func, *args).result()


_PortalFactoryType = Callable[[], AbstractContextManager[_BlockingPortal]]


class _Upgrade(Exception):
    def __init__(self, session: "WebSocketTestSession") -> None:
        self.session = session


class WebSocketDenialResponse(WebSocketDisconnect):
    def __init__(self, response: zapros.Response) -> None:
        super().__init__(code=1000, reason="")
        self.response = TestResponse(response)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.response, name)


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
        self._task: asyncio.Task[None] | None = None
        self._closing = False

    def __enter__(self) -> Self:
        with contextlib.ExitStack() as stack:
            self.portal = portal = stack.enter_context(self.portal_factory())
            self._receive_queue = portal.call(asyncio.Queue[Message])
            self._send_queue = portal.call(asyncio.Queue[Message | BaseException])
            fut = portal.start_task_soon(self._run)
            stack.callback(fut.result)
            stack.callback(portal.call, self._cancel)
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

    async def _run(self) -> None:
        self._task = asyncio.current_task()
        try:
            await self.app(self.scope, self._receive_queue.get, self._send_queue.put)
            await asyncio.get_running_loop().create_future()
        except asyncio.CancelledError:
            if not self._closing:
                raise
        except BaseException as exc:
            self._send_queue.put_nowait(exc)
            raise

    def _cancel(self) -> None:
        self._closing = True
        if self._task is not None:
            self._task.cancel()

    def send(self, message: Message) -> None:
        self.portal.call(self._receive_queue.put, message)

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
        message = self.portal.call(self._send_queue.get)
        if isinstance(message, BaseException):
            raise message
        return message

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
            raw_headers: list[tuple[bytes, bytes]] = message["headers"]
            body: list[bytes] = []
            while True:
                message = self.receive()
                if message["type"] != "websocket.http.response.body":
                    raise RuntimeError(f'Expected "websocket.http.response.body", got: {message["type"]!r}')
                body.append(message["body"])
                if not message.get("more_body", False):
                    break
            headers = [(key.decode(), value.decode()) for key, value in raw_headers]
            response = _build_response(status_code, headers, b"".join(body))
            response.read()
            raise WebSocketDenialResponse(response)


def _build_response(
    status: int,
    headers: list[tuple[str, str]],
    body: bytes,
    request: zapros.Request | None = None,
) -> zapros.Response:
    response = zapros.Response(status, content=body or None, request=request)
    response.headers = zapros.Headers(headers)
    return response


class Cookies(MutableMapping[str, str]):
    def __init__(self, cookies: "CookieTypes | None" = None) -> None:
        if isinstance(cookies, Cookies):
            self.jar = cookies.jar
        elif isinstance(cookies, CookieJar):
            self.jar = cookies
        else:
            self.jar = CookieJar()
            if cookies is not None:
                items = cookies.items() if isinstance(cookies, Mapping) else cookies
                for name, value in items:
                    self.set(name, value)

    def set(self, name: str, value: str, domain: str = "", path: str = "/") -> None:
        self.jar.set_cookie(
            Cookie(
                version=0,
                name=name,
                value=value,
                port=None,
                port_specified=False,
                domain=domain,
                domain_specified=bool(domain),
                domain_initial_dot=domain.startswith("."),
                path=path,
                path_specified=bool(path),
                secure=False,
                expires=None,
                discard=True,
                comment=None,
                comment_url=None,
                rest={"HttpOnly": None},
                rfc2109=False,
            )
        )

    def get(
        self,
        name: str,
        default: str | None = None,
        domain: str | None = None,
        path: str | None = None,
    ) -> str | None:
        for cookie in self.jar:
            if (
                cookie.name == name
                and (domain is None or cookie.domain == domain)
                and (path is None or cookie.path == path)
            ):
                return cookie.value
        return default

    def delete(self, name: str, domain: str | None = None, path: str | None = None) -> None:
        remove = [
            cookie
            for cookie in self.jar
            if cookie.name == name
            and (domain is None or cookie.domain == domain)
            and (path is None or cookie.path == path)
        ]
        for cookie in remove:
            self.jar.clear(cookie.domain, cookie.path, cookie.name)

    def clear(self, domain: str | None = None, path: str | None = None) -> None:
        if domain is None:
            self.jar.clear()
        elif path is None:
            self.jar.clear(domain)
        else:
            self.jar.clear(domain, path)

    def update(self, cookies: Any = None, /, **kwargs: str) -> None:
        other = Cookies(cookies)
        for cookie in other.jar:
            self.jar.set_cookie(cookie)
        for name, value in kwargs.items():
            self.set(name, value)

    def __getitem__(self, name: str) -> str:
        value = self.get(name)
        if value is None:
            raise KeyError(name)
        return value

    def __setitem__(self, name: str, value: str) -> None:
        self.set(name, value)

    def __delitem__(self, name: str) -> None:
        if self.get(name) is None:
            raise KeyError(name)
        self.delete(name)

    def __len__(self) -> int:
        return len(self.jar)

    def __iter__(self) -> Iterator[str]:
        return (cookie.name for cookie in self.jar)

    def __bool__(self) -> bool:
        return any(True for _ in self.jar)

    def __repr__(self) -> str:
        return f"<Cookies[{', '.join(f'{c.name}={c.value}' for c in self.jar)}]>"


CookieTypes = Cookies | CookieJar | Mapping[str, str] | Sequence[tuple[str, str]]


class _MockHTTPResponse:
    def __init__(self, headers: Any) -> None:
        self.msg = headers

    def info(self) -> Any:
        return self.msg


class TestResponse:
    __test__ = False

    def __init__(self, response: zapros.Response) -> None:
        self._response = response
        debug_info = response.context.get("http.response.debug")
        self.extensions: dict[str, Any] = {}
        if debug_info is not None:
            self.extensions["http.response.debug"] = debug_info
            if "template" in debug_info:
                self.template = debug_info["template"]
            if "context" in debug_info:
                self.context = debug_info["context"]

    @property
    def zapros_response(self) -> zapros.Response:
        return self._response

    @property
    def status_code(self) -> int:
        return self._response.status

    @property
    def reason_phrase(self) -> str:
        try:
            return HTTPStatus(self._response.status).phrase
        except ValueError:
            return ""

    @property
    def content(self) -> bytes:
        return self._response.read()

    def read(self) -> bytes:
        return self._response.read()

    @property
    def text(self) -> str:
        self._response.read()
        return self._response.text

    def json(self, **kwargs: Any) -> Any:
        return json.loads(self.text, **kwargs)

    def iter_lines(self) -> Iterator[str]:
        yield from self.text.splitlines()

    @property
    def url(self) -> str | None:
        request = self._response.request
        return None if request is None else str(request.url)

    @functools.cached_property
    def cookies(self) -> Cookies:
        cookies = Cookies()
        request = self._response.request
        if request is None:
            return cookies
        message = HTTPMessage()
        for value in self._response.headers.getall("set-cookie"):
            message["Set-Cookie"] = value
        cookies.jar.extract_cookies(_MockHTTPResponse(message), UrllibRequest(str(request.url)))
        return cookies

    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)

    def __repr__(self) -> str:
        return f"<Response [{self.status_code}]>"


def _primitive_to_str(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return ""
    return str(value)


def _form_items(data: Mapping[str, Any]) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for key, value in data.items():
        values = value if isinstance(value, (list, tuple)) else [value]
        items.extend((str(key), _primitive_to_str(item)) for item in values)
    return items


def _format_form_param(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "%22")


def _file_part(value: Any) -> tuple[str | None, bytes, str]:
    if isinstance(value, tuple):
        filename, content, *rest = value
        content_type = rest[0] if rest and rest[0] is not None else None
    else:
        content = value
        filename = getattr(value, "name", None)
        filename = os.path.basename(filename) if isinstance(filename, str) else "upload"
        content_type = None
    if hasattr(content, "read"):
        content = content.read()
    if isinstance(content, str):
        content = content.encode("utf-8")
    if content_type is None:
        content_type = (mimetypes.guess_type(filename)[0] if filename else None) or "application/octet-stream"
    return filename, content, content_type


def _encode_multipart(data: Mapping[str, Any] | None, files: Any) -> tuple[bytes, str]:
    boundary = os.urandom(16).hex()
    chunks: list[bytes] = []
    for name, value in _form_items(data or {}):
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{_format_form_param(name)}"\r\n\r\n'.encode()
            + value.encode("utf-8")
            + b"\r\n"
        )
    file_items = files.items() if isinstance(files, Mapping) else files
    for name, value in file_items:
        filename, content, content_type = _file_part(value)
        disposition = f'form-data; name="{_format_form_param(name)}"'
        if filename is not None:
            disposition += f'; filename="{_format_form_param(filename)}"'
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: {disposition}\r\nContent-Type: {content_type}\r\n\r\n".encode()
            + content
            + b"\r\n"
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _encode_body(
    content: Any,
    data: Any,
    files: Any,
    json_data: Any,
) -> tuple[bytes | Iterator[bytes] | None, str | None]:
    if content is not None:
        if isinstance(content, str):
            return content.encode("utf-8"), None
        if isinstance(content, (bytes, bytearray, memoryview)):
            return bytes(content), None
        return iter(content), None
    if files:
        return _encode_multipart(data, files)
    if data is not None:
        if isinstance(data, (str, bytes)):
            return data.encode("utf-8") if isinstance(data, str) else data, None
        return urlencode(_form_items(data)).encode("ascii"), "application/x-www-form-urlencoded"
    if json_data is not None:
        body = json.dumps(json_data, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return body, "application/json"
    return None, None


def _to_header_pairs(headers: Any) -> list[tuple[str, str]]:
    if headers is None:
        return []
    if isinstance(headers, zapros.Headers):
        return _header_pairs(headers)
    if isinstance(headers, Mapping):
        return [(str(key), str(value)) for key, value in headers.items()]
    return [(str(key), str(value)) for key, value in headers]


def _header_pairs(headers: zapros.Headers) -> list[tuple[str, str]]:
    return [(key, value) for key in headers for value in headers.getall(key)]


async def _read_request_body(request: zapros.Request) -> bytes:
    body = request.body
    if body is None:
        return b""
    if isinstance(body, bytes):
        return body
    if isinstance(body, AsyncIterator):
        return b"".join([chunk async for chunk in body])
    return b"".join(body)


class _TestClientTransport(zapros.BaseHandler):
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

    def handle(self, request: zapros.Request) -> zapros.Response:
        url = request.url
        scheme = url.protocol[:-1]
        host = url.hostname.removeprefix("[").removesuffix("]")
        raw_path = url.pathname.encode("utf-8") or b"/"
        path = unquote(url.pathname) or "/"
        query = url.search[1:]
        port = int(url.port) if url.port else _DEFAULT_PORTS[scheme]

        headers = [(key.lower().encode(), value.encode()) for key, value in _header_pairs(request.headers)]

        scope: dict[str, Any]

        if scheme in {"ws", "wss"}:
            subprotocol = request.headers.get("sec-websocket-protocol", None)
            if subprotocol is None:
                subprotocols: Sequence[str] = []
            else:
                subprotocols = [value.strip() for value in subprotocol.split(",")]
            scope = {
                "type": "websocket",
                "path": path,
                "raw_path": raw_path,
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
            "path": path,
            "raw_path": raw_path,
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
        response_complete: asyncio.Event
        status_code = 500
        response_headers: list[tuple[str, str]] = []
        body_chunks: list[bytes] = []
        debug_info: dict[str, Any] | None = None

        async def receive() -> Message:
            nonlocal request_complete

            if request_complete:
                if not response_complete.is_set():
                    await response_complete.wait()
                return {"type": "http.disconnect"}

            body_bytes = await _read_request_body(request)
            request_complete = True
            return {"type": "http.request", "body": body_bytes}

        async def send(message: Message) -> None:
            nonlocal status_code, response_headers, response_started, debug_info

            if message["type"] == "http.response.start":
                if response_started:
                    raise RuntimeError('Received multiple "http.response.start" messages.')
                status_code = message["status"]
                response_headers = [(key.decode(), value.decode()) for key, value in message.get("headers", [])]
                response_started = True
            elif message["type"] == "http.response.body":
                if not response_started:
                    raise RuntimeError('Received "http.response.body" without "http.response.start".')
                if response_complete.is_set():
                    raise RuntimeError('Received "http.response.body" after response completed.')
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if request.method != "HEAD":
                    body_chunks.append(body)
                if not more_body:
                    response_complete.set()
            elif message["type"] == "http.response.debug":
                debug_info = message["info"]

        try:
            with self.portal_factory() as portal:
                response_complete = portal.call(asyncio.Event)
                portal.call(self.app, scope, receive, send)
        except BaseException:
            if self.raise_server_exceptions:
                raise

        if self.raise_server_exceptions and not response_started:
            raise RuntimeError("TestClient did not receive any response.")
        elif not response_started:
            status_code, response_headers, body_chunks = 500, [], []

        response = _build_response(status_code, response_headers, b"".join(body_chunks), request)
        if debug_info is not None:
            response.context["http.response.debug"] = debug_info
        return response


def _default_accept_encoding() -> str:
    encodings = ["gzip", "deflate"]
    if any(module in sys.modules for module in ("brotli", "brotlicffi")):
        encodings.append("br")
    encodings.append("zstd")
    return ", ".join(encodings)


class TestClient(zapros.Client):
    __test__ = False
    task: Future[None]
    portal: _BlockingPortal | None = None

    def __init__(
        self,
        app: ASGI3App,
        base_url: str = "http://testserver",
        raise_server_exceptions: bool = True,
        root_path: str = "",
        cookies: CookieTypes | None = None,
        headers: dict[str, str] | None = None,
        follow_redirects: bool = True,
        client: tuple[str, int] = ("testclient", 50000),
    ) -> None:
        self.app: ASGI3App = app
        self.app_state: dict[str, Any] = {}
        self.follow_redirects = follow_redirects
        self._cookies = Cookies(cookies)

        self._transport = _TestClientTransport(
            self.app,
            portal_factory=self._portal_factory,
            raise_server_exceptions=raise_server_exceptions,
            root_path=root_path,
            app_state=self.app_state,
            client=client,
        )

        default_headers = {
            "accept": "*/*",
            "accept-encoding": _default_accept_encoding(),
            "connection": "keep-alive",
            "user-agent": "testclient",
        }
        super().__init__(
            handler=self._build_handler(self._cookies.jar, follow_redirects),
            base_url=base_url,
            default_headers=default_headers,
        )
        if headers is not None:
            for key, value in _to_header_pairs(headers):
                self.default_headers[key] = value

    def _build_handler(self, jar: CookieJar, follow_redirects: bool) -> zapros.BaseHandler:
        handler: zapros.BaseHandler = zapros.CookieMiddleware(self._transport, jar=jar)
        if follow_redirects:
            handler = zapros.RedirectMiddleware(handler)
        return handler

    @property
    def headers(self) -> zapros.Headers:
        return self.default_headers

    @headers.setter
    def headers(self, headers: Any) -> None:
        self.default_headers = zapros.Headers(_to_header_pairs(headers))

    @property
    def cookies(self) -> Cookies:
        return self._cookies

    @cookies.setter
    def cookies(self, cookies: CookieTypes | None) -> None:
        new = Cookies(cookies)
        if new.jar is self._cookies.jar:
            return
        self._cookies.jar.clear()
        for cookie in new.jar:
            self._cookies.jar.set_cookie(cookie)

    def _merge_url(self, url: str | URL, params: Any = None) -> URL:
        if isinstance(url, str) and self.base_url and not urlsplit(url).scheme:
            base = self.base_url if self.base_url.endswith("/") else self.base_url + "/"
            url = base + url.lstrip("/")
        return super()._merge_url(url, params)

    def _merge_headers(self, headers: Any, auth: str | tuple[str, str] | None = None) -> zapros.Headers:
        pairs = _to_header_pairs(headers)
        merged = super()._merge_headers(None, auth=auth)
        for key in {key.lower() for key, _ in pairs}:
            merged.pop(key, None)
        for key, value in pairs:
            merged.add(key, value)
        return merged

    @contextlib.contextmanager
    def _portal_factory(self) -> Generator[_BlockingPortal]:
        if self.portal is not None:
            yield self.portal
        else:
            with _BlockingPortal() as portal:
                yield portal

    def build_request(
        self,
        method: str,
        url: str | URL,
        *,
        content: Any = None,
        data: Any = None,
        files: Any = None,
        json: Any = None,
        params: Any = None,
        headers: Any = None,
        cookies: CookieTypes | None = None,
        auth: str | tuple[str, str] | None = None,
        timeout: Any = None,
        extensions: Any = None,
    ) -> zapros.Request:
        body, content_type = _encode_body(content, data, files, json)
        pairs = _to_header_pairs(headers)
        names = {key.lower() for key, _ in pairs}
        if content_type is not None and "content-type" not in names:
            pairs.append(("Content-Type", content_type))
        if cookies:
            cookie_header = "; ".join(f"{name}={value}" for name, value in Cookies(cookies).items())
            pairs.append(("Cookie", cookie_header))
        request_url = self._merge_url(url, params)
        merged_headers = self._merge_headers(pairs, auth=auth)
        if body is None:
            return zapros.Request(request_url, method, headers=merged_headers)
        return zapros.Request(request_url, method, headers=merged_headers, body=body)

    def send(
        self,
        request: zapros.Request,
        *,
        follow_redirects: bool | None = None,
        auth: Any = None,
        stream: bool = False,
    ) -> TestResponse:
        if follow_redirects is None or follow_redirects == self.follow_redirects:
            handler = self.handler
        else:
            handler = self._build_handler(self._cookies.jar, follow_redirects)
        try:
            response = handler.handle(request)
            try:
                response.read()
            finally:
                response.close()
        finally:
            if isinstance(request.body, zapros.ClosableStream):
                request.body.close()
        return TestResponse(response)

    def request(
        self,
        method: str,
        url: str | URL,
        *,
        follow_redirects: bool | None = None,
        **kwargs: Any,
    ) -> TestResponse:
        return self.send(self.build_request(method, url, **kwargs), follow_redirects=follow_redirects)

    @contextlib.contextmanager
    def stream(self, method: str, url: str | URL, **kwargs: Any) -> Generator[TestResponse]:
        yield self.request(method, url, **kwargs)

    def get(self, url: str | URL, **kwargs: Any) -> TestResponse:
        return self.request("GET", url, **kwargs)

    def options(self, url: str | URL, **kwargs: Any) -> TestResponse:
        return self.request("OPTIONS", url, **kwargs)

    def head(self, url: str | URL, **kwargs: Any) -> TestResponse:
        return self.request("HEAD", url, **kwargs)

    def post(self, url: str | URL, **kwargs: Any) -> TestResponse:
        return self.request("POST", url, **kwargs)

    def put(self, url: str | URL, **kwargs: Any) -> TestResponse:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str | URL, **kwargs: Any) -> TestResponse:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str | URL, **kwargs: Any) -> TestResponse:
        return self.request("DELETE", url, **kwargs)

    def websocket_connect(
        self,
        url: str,
        subprotocols: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> WebSocketTestSession:
        url = urljoin("ws://testserver", url)
        headers = _to_header_pairs(kwargs.get("headers"))
        names = {key.lower() for key, _ in headers}
        defaults = [
            ("connection", "upgrade"),
            ("sec-websocket-key", "testserver=="),
            ("sec-websocket-version", "13"),
        ]
        if subprotocols is not None:
            defaults.append(("sec-websocket-protocol", ", ".join(subprotocols)))
        headers.extend((key, value) for key, value in defaults if key not in names)
        kwargs["headers"] = headers
        try:
            self.request("GET", url, **kwargs)
        except _Upgrade as exc:
            return exc.session
        raise RuntimeError("Expected WebSocket upgrade")

    def __enter__(self) -> Self:
        with contextlib.ExitStack() as stack:
            self.portal = portal = stack.enter_context(_BlockingPortal())

            @stack.callback
            def reset_portal() -> None:
                self.portal = None

            self._lifespan_to_app = portal.call(asyncio.Queue[Message])
            self._lifespan_from_app = portal.call(asyncio.Queue[Message | BaseException | None])
            self.task = portal.start_task_soon(self.lifespan)
            portal.call(self.wait_startup)

            @stack.callback
            def wait_shutdown() -> None:
                portal.call(self.wait_shutdown)

            self.exit_stack = stack.pop_all()

        return self

    def __exit__(self, *args: Any) -> None:
        try:
            self.exit_stack.close()
        finally:
            self.close()

    async def lifespan(self) -> None:
        scope = {"type": "lifespan", "state": self.app_state}
        try:
            await self.app(scope, self._lifespan_to_app.get, self._lifespan_from_app.put)
        except BaseException as exc:
            self._lifespan_from_app.put_nowait(exc)
            raise
        else:
            self._lifespan_from_app.put_nowait(None)

    async def wait_startup(self) -> None:
        await self._lifespan_to_app.put({"type": "lifespan.startup"})

        message = await self._receive_lifespan_message()
        if message["type"] not in ("lifespan.startup.complete", "lifespan.startup.failed"):
            raise RuntimeError(f"Unexpected message during lifespan startup: {message['type']!r}")
        if message["type"] == "lifespan.startup.failed":
            await self._receive_lifespan_message()

    async def wait_shutdown(self) -> None:
        await self._lifespan_to_app.put({"type": "lifespan.shutdown"})
        message = await self._receive_lifespan_message()
        if message["type"] not in ("lifespan.shutdown.complete", "lifespan.shutdown.failed"):
            raise RuntimeError(f"Unexpected message during lifespan shutdown: {message['type']!r}")
        if message["type"] == "lifespan.shutdown.failed":
            await self._receive_lifespan_message()

    async def _receive_lifespan_message(self) -> Message:
        message = await self._lifespan_from_app.get()
        if isinstance(message, BaseException):
            raise message
        return cast(Message, message)
