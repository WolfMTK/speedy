import functools
import inspect
import re
import traceback
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Collection, Sequence
from enum import Enum
from typing import Any

from speedy._exception_handler import wrap_app_handling_exceptions
from speedy._speedy import HTTPConnection, URLPath
from speedy.concurrency import is_async_callable, run_in_threadpool
from speedy.convertors import CONVERTOR_TYPES, Convertor
from speedy.datastructures import Headers
from speedy.exceptions import HTTPException
from speedy.helpers import get_route_path, parse_host_header
from speedy.middleware import Middleware
from speedy.middleware.body_limit import RequestBodyLimitMiddleware
from speedy.requests import Request
from speedy.responses import PlainTextResponse, RedirectResponse, Response
from speedy.types import ASGIApplication, BaseScope, Lifespan, Receive, Scope, Send
from speedy.websocket import WebSocket, WebSocketClose

_URLPATH_BASE = "http://"


class NoMatchFound(Exception):
    def __init__(self, name: str, path_params: dict[str, Any]) -> None:
        params = ", ".join(list(path_params.keys()))
        super().__init__(f'No route exists for name "{name}" and params "{params}".')


class Match(Enum):
    NONE = 0
    PARTIAL = 1
    FULL = 2


def request_response(func: Callable[[Request], Awaitable[Response] | Response]) -> ASGIApplication:
    f: Callable[[Request], Awaitable[Response]] = (
        func if is_async_callable(func) else functools.partial(run_in_threadpool, func)
    )

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive, send)

        async def inner_app(scope: Scope, receive: Receive, send: Send) -> None:
            response = await f(request)
            await response(scope, receive, send)

        await wrap_app_handling_exceptions(inner_app, request)(scope, receive, send)

    return app


def websocket_session(func: Callable[[WebSocket], Awaitable[None]]) -> ASGIApplication:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        session = WebSocket(scope, receive, send)

        async def inner_app(scope: Scope, receive: Receive, send: Send) -> None:
            await func(session)

        await wrap_app_handling_exceptions(inner_app, session)(scope, receive, send)

    return app


def get_name(endpoint: Callable[..., Any]) -> str:
    return getattr(endpoint, "__name__", type(endpoint).__name__)


_PARAM_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def replace_params(
    path: str,
    param_convertors: dict[str, Convertor[Any]],
    path_params: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    remaining_params = dict(path_params)

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in remaining_params:
            return match.group(0)
        convertor = param_convertors[key]
        return convertor.to_string(remaining_params.pop(key))

    new_path = _PARAM_PLACEHOLDER_RE.sub(substitute, path)
    return new_path, remaining_params


PARAM_REGEX = re.compile("{([a-zA-Z_][a-zA-Z0-9_]*)(:[a-zA-Z_][a-zA-Z0-9_]*)?}")


def compile_path(path: str) -> tuple[re.Pattern[str], str, dict[str, Convertor[Any]]]:
    is_host = not path.startswith("/")

    path_regex = "^"
    path_format = ""
    duplicated_params: set[str] = set()

    idx = 0
    param_convertors = {}
    for match in PARAM_REGEX.finditer(path):
        param_name, convertor_type = match.groups("str")
        convertor_type = convertor_type.lstrip(":")
        if convertor_type not in CONVERTOR_TYPES:
            raise ValueError(f"Unknown path convertor {convertor_type!r}")
        convertor = CONVERTOR_TYPES[convertor_type]

        path_regex += re.escape(path[idx : match.start()])
        path_regex += f"(?P<{param_name}>{convertor.regex})"

        path_format += path[idx : match.start()]
        path_format += f"{{{param_name}}}"

        if param_name in param_convertors:
            duplicated_params.add(param_name)

        param_convertors[param_name] = convertor

        idx = match.end()

    if duplicated_params:
        names = ", ".join(sorted(duplicated_params))
        ending = "s" if len(duplicated_params) > 1 else ""
        raise ValueError(f"Duplicated param name{ending} {names} at path {path}")

    if is_host:
        hostname = path[idx:]
        if not hostname.endswith("]"):
            hostname = hostname.rsplit(":", 1)[0]
        path_regex += re.escape(hostname) + "$"
    else:
        path_regex += re.escape(path[idx:]) + "$"

    path_format += path[idx:]

    return re.compile(path_regex), path_format, param_convertors


class BaseRoute[ScopeT: BaseScope](ABC):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        match, child_scope = self.matches(scope)
        if match == Match.NONE:
            if scope["type"] == "http":
                response = PlainTextResponse("Not Found", status_code=404)
                await response(scope, receive, send)
            elif scope["type"] == "websocket":
                websocket_close = WebSocketClose()
                await websocket_close(scope, receive, send)
            return

        scope.update(child_scope)
        await self.handle(scope, receive, send)

    @abstractmethod
    def matches(self, scope: Scope) -> tuple[Match, dict[str, Any]]: ...

    @abstractmethod
    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath: ...

    @abstractmethod
    async def handle(
        self,
        scope: ScopeT,
        receive: Receive,
        send: Send,
    ) -> None: ...


class Route(BaseRoute):
    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        methods: Collection[str] | None = None,
        name: str | None = None,
        include_in_schema: bool = True,
        middleware: Sequence[Middleware] | None = None,
        max_body_size: int | None = None,
    ) -> None:
        if not path.startswith("/"):
            raise ValueError("Routed paths must start with '/'")
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint) if name is None else name
        self.include_in_schema = include_in_schema

        endpoint_handler = endpoint
        while isinstance(endpoint_handler, functools.partial):
            endpoint_handler = endpoint_handler.func
        if inspect.isfunction(endpoint_handler) or inspect.ismethod(endpoint_handler):
            self.app: ASGIApplication = request_response(endpoint)
            if methods is None:
                methods = ["GET"]
        else:
            self.app = endpoint

        if middleware is not None:
            for cls, args, kwargs in reversed(middleware):
                self.app = cls(self.app, *args, **kwargs)
        if max_body_size is not None:
            self.app = RequestBodyLimitMiddleware(self.app, max_body_size=max_body_size)

        if methods is None:
            self.methods = None
        else:
            self.methods = {method.upper() for method in methods}
            if "GET" in self.methods:
                self.methods.add("HEAD")

        self.path_regex, self.path_format, self.param_convertors = compile_path(path)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, Route)
            and self.path == other.path
            and self.endpoint == other.endpoint
            and self.methods == other.methods
        )

    def __repr__(self) -> str:
        class_name = type(self).__name__
        methods = sorted(self.methods or [])
        return f"{class_name}(path={self.path!r}, name={self.name!r}, methods={methods!r})"

    def matches(self, scope: Scope) -> tuple[Match, dict[str, Any]]:
        path_params: dict[str, Any]
        if scope["type"] == "http":
            route_path = get_route_path(scope)
            match = self.path_regex.match(route_path)
            if match:
                matched_params = match.groupdict()
                for key, value in matched_params.items():
                    matched_params[key] = self.param_convertors[key].convert(value)
                path_params = dict(scope.get("path_params", {}))  # type: ignore[call-overload]
                path_params.update(matched_params)
                child_scope = {"endpoint": self.endpoint, "path_params": path_params}
                if self.methods and scope["method"] not in self.methods:  # type: ignore[typeddict-item]
                    return Match.PARTIAL, child_scope
                return Match.FULL, child_scope
        return Match.NONE, {}

    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath:
        seen_params = set(path_params.keys())
        expected_params = set(self.param_convertors.keys())

        if name != self.name or seen_params != expected_params:
            raise NoMatchFound(name, path_params)

        path, remaining_params = replace_params(self.path_format, self.param_convertors, path_params)
        if remaining_params:
            raise NoMatchFound(name, path_params)
        return URLPath(path, base=_URLPATH_BASE)

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.methods and scope["method"] not in self.methods:  # type: ignore[typeddict-item]
            headers = {"Allow": ", ".join(self.methods)}
            if "app" in scope:
                raise HTTPException(status_code=405, headers=headers)
            response = PlainTextResponse("Method Not Allowed", status_code=405, headers=headers)
            await response(scope, receive, send)
        else:
            await self.app(scope, receive, send)


class WebSocketRoute(BaseRoute):
    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        name: str | None = None,
        middleware: Sequence[Middleware] | None = None,
    ) -> None:
        if not path.startswith("/"):
            raise ValueError("Routed paths must start with '/'")
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint) if name is None else name

        endpoint_handler = endpoint
        while isinstance(endpoint_handler, functools.partial):
            endpoint_handler = endpoint_handler.func
        if inspect.isfunction(endpoint_handler) or inspect.ismethod(endpoint_handler):
            self.app: ASGIApplication = websocket_session(endpoint)
        else:
            self.app = endpoint

        if middleware is not None:
            for cls, args, kwargs in reversed(middleware):
                self.app = cls(self.app, *args, **kwargs)

        self.path_regex, self.path_format, self.param_convertors = compile_path(path)

    def matches(self, scope: Scope) -> tuple[Match, dict[str, Any]]:
        path_params: dict[str, Any]
        if scope["type"] == "websocket":
            route_path = get_route_path(scope)
            match = self.path_regex.match(route_path)
            if match:
                matched_params = match.groupdict()
                for key, value in matched_params.items():
                    matched_params[key] = self.param_convertors[key].convert(value)
                path_params = dict(scope.get("path_params", {}))
                path_params.update(matched_params)
                child_scope = {"endpoint": self.endpoint, "path_params": path_params}
                return Match.FULL, child_scope
        return Match.NONE, {}

    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath:
        seen_params = set(path_params.keys())
        expected_params = set(self.param_convertors.keys())

        if name != self.name or seen_params != expected_params:
            raise NoMatchFound(name, path_params)

        path, remaining_params = replace_params(self.path_format, self.param_convertors, path_params)
        if remaining_params:
            raise NoMatchFound(name, path_params)
        return URLPath(path, base=_URLPATH_BASE)

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, WebSocketRoute) and self.path == other.path and self.endpoint == other.endpoint

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path!r}, name={self.name!r})"


class Mount(BaseRoute):
    def __init__(
        self,
        path: str,
        app: ASGIApplication | None = None,
        routes: Sequence[BaseRoute] | None = None,
        name: str | None = None,
        *,
        middleware: Sequence[Middleware] | None = None,
        max_body_size: int | None = None,
    ) -> None:
        if path != "" and not path.startswith("/"):
            raise ValueError("Routed paths must start with '/'")
        if app is None and routes is None:
            raise ValueError("Either 'app=...', or 'routes=' must be specified")
        self.path = path.rstrip("/")
        self._base_app: ASGIApplication = app if app is not None else Router(routes=routes)
        self.app: ASGIApplication = self._base_app
        if middleware is not None:
            for cls, args, kwargs in reversed(middleware):
                self.app = cls(self.app, *args, **kwargs)
        if max_body_size is not None:
            self.app = RequestBodyLimitMiddleware(self.app, max_body_size=max_body_size)
        self.name = name
        self.path_regex, self.path_format, self.param_convertors = compile_path(self.path + "/{path:path}")

    @property
    def routes(self) -> list[BaseRoute]:
        return getattr(self._base_app, "routes", [])

    def matches(self, scope: Scope) -> tuple[Match, dict[str, Any]]:
        path_params: dict[str, Any]
        if scope["type"] in {"http", "websocket"}:
            root_path: str = scope.get("root_path", "")
            route_path = get_route_path(scope)
            match = self.path_regex.match(route_path)
            if match:
                matched_params = match.groupdict()
                for key, value in matched_params.items():
                    matched_params[key] = self.param_convertors[key].convert(value)
                remaining_path = "/" + matched_params.pop("path")
                matched_path = route_path[: -len(remaining_path)]
                path_params = dict(scope.get("path_params", {}))  # type: ignore[call-overload]
                path_params.update(matched_params)
                child_scope = {
                    "path_params": path_params,
                    "app_root_path": scope.get("app_root_path", root_path),  # type: ignore[typeddict-item]
                    "root_path": root_path + matched_path,
                    "endpoint": self.app,
                }
                return Match.FULL, child_scope
        return Match.NONE, {}

    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath:
        if self.name is not None and name == self.name and "path" in path_params:
            path_params["path"] = path_params["path"].lstrip("/")
            path, remaining_params = replace_params(self.path_format, self.param_convertors, path_params)
            if not remaining_params:
                return URLPath(path, base=_URLPATH_BASE)
        elif self.name is None or name.startswith(self.name + ":"):
            remaining_name = name if self.name is None else name[len(self.name) + 1 :]
            path_kwarg = path_params.get("path")
            path_params["path"] = ""
            path_prefix, remaining_params = replace_params(self.path_format, self.param_convertors, path_params)
            if path_kwarg is not None:
                remaining_params["path"] = path_kwarg
            for route in self.routes or []:
                try:
                    url = route.url_path_for(remaining_name, **remaining_params)
                    return URLPath(path_prefix.rstrip("/") + str(url.path), base=_URLPATH_BASE)
                except NoMatchFound:
                    pass
        raise NoMatchFound(name, path_params)

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Mount) and self.path == other.path and self.app == other.app

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        name = self.name or ""
        return f"{class_name}(path={self.path!r}, name={name!r}, app={self.app!r})"


class Host(BaseRoute):
    def __init__(self, host: str, app: ASGIApplication, name: str | None = None) -> None:
        if host.startswith("/"):
            raise ValueError("Host must not start with '/'")
        self.host = host
        self.app = app
        self.name = name
        self.host_regex, self.host_format, self.param_convertors = compile_path(host)

    @property
    def routes(self) -> list[BaseRoute]:
        return getattr(self.app, "routes", [])

    def matches(self, scope: Scope) -> tuple[Match, dict[str, Any]]:
        if scope["type"] in {"http", "websocket"}:
            headers = Headers(scope=scope)
            parsed_host = parse_host_header(headers.get("host"))
            if parsed_host is None:
                return Match.NONE, {}

            match = self.host_regex.match(parsed_host.host)
            if match:
                matched_params = match.groupdict()
                for key, value in matched_params.items():
                    matched_params[key] = self.param_convertors[key].convert(value)
                path_params = dict(scope.get("path_params", {}))  # type: ignore[call-overload]
                path_params.update(matched_params)
                child_scope = {"path_params": path_params, "endpoint": self.app}
                return Match.FULL, child_scope
        return Match.NONE, {}

    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath:
        if self.name is not None and name == self.name and "path" in path_params:
            path = path_params.pop("path")
            _host, remaining_params = replace_params(self.host_format, self.param_convertors, path_params)
            if not remaining_params:
                return URLPath(path, base=_URLPATH_BASE)
        elif self.name is None or name.startswith(self.name + ":"):
            remaining_name = name if self.name is None else name[len(self.name) + 1 :]
            _host, remaining_params = replace_params(self.host_format, self.param_convertors, path_params)
            for route in self.routes or []:
                try:
                    url = route.url_path_for(remaining_name, **remaining_params)
                    return URLPath(str(url.path), base=_URLPATH_BASE)
                except NoMatchFound:
                    pass
        raise NoMatchFound(name, path_params)

    async def handle(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app(scope, receive, send)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Host) and self.host == other.host and self.app == other.app

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        name = self.name or ""
        return f"{class_name}(host={self.host!r}, name={name!r}, app={self.app!r})"


class _DefaultLifespan:
    def __init__(self, router: "Router") -> None:
        self._router = router

    async def __aenter__(self) -> None:
        pass

    async def __aexit__(self, *exc_info: object) -> None:
        pass

    def __call__[T](self: T, app: object) -> T:
        return self


class Router:
    def __init__(
        self,
        routes: Sequence[BaseRoute] | None = None,
        redirect_slashes: bool = True,
        default: ASGIApplication | None = None,
        lifespan: Lifespan | None = None,
        *,
        middleware: Sequence[Middleware] | None = None,
        max_body_size: int | None = None,
    ) -> None:
        self.routes = [] if routes is None else list(routes)
        self.redirect_slashes = redirect_slashes
        self.default = self.not_found if default is None else default

        self.lifespan_context: Any = _DefaultLifespan(self) if lifespan is None else lifespan

        self.middleware_stack: ASGIApplication = self.app
        if middleware:
            for cls, args, kwargs in reversed(middleware):
                self.middleware_stack = cls(self.middleware_stack, *args, **kwargs)
        if max_body_size is not None:
            self.middleware_stack = RequestBodyLimitMiddleware(self.middleware_stack, max_body_size=max_body_size)

    async def not_found(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            websocket_close = WebSocketClose()
            await websocket_close(scope, receive, send)  # type: ignore[arg-type]
            return

        if "app" in scope:
            raise HTTPException(status_code=404)
        response = PlainTextResponse("Not Found", status_code=404)
        await response(scope, receive, send)

    def url_path_for(self, name: str, /, **path_params: Any) -> URLPath:
        for route in self.routes:
            try:
                return route.url_path_for(name, **path_params)
            except NoMatchFound:
                pass
        raise NoMatchFound(name, path_params)

    async def lifespan(self, scope: Scope, receive: Receive, send: Send) -> None:
        started = False
        app: Any = scope.get("app")
        await receive()
        try:
            async with self.lifespan_context(app) as maybe_state:
                if maybe_state is not None:
                    if "state" not in scope:
                        raise RuntimeError('The server does not support "state" in the lifespan scope.')
                    scope["state"].update(maybe_state)  # type: ignore[typeddict-item]
                await send({"type": "lifespan.startup.complete"})
                started = True
                await receive()
        except BaseException:
            exc_text = traceback.format_exc()
            if started:
                await send({"type": "lifespan.shutdown.failed", "message": exc_text})
            else:
                await send({"type": "lifespan.startup.failed", "message": exc_text})
            raise
        else:
            await send({"type": "lifespan.shutdown.complete"})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.middleware_stack(scope, receive, send)

    async def app(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket", "lifespan"}:
            raise ValueError(f"Unsupported scope type {scope['type']!r}")

        if "router" not in scope:
            scope["router"] = self  # type: ignore[typeddict-item]

        if scope["type"] == "lifespan":
            await self.lifespan(scope, receive, send)
            return

        partial = None
        partial_scope: dict[str, Any] = {}

        for route in self.routes:
            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                scope["route"] = route  # type: ignore[typeddict-item]
                scope.update(child_scope)
                await route.handle(scope, receive, send)
                return
            if match == Match.PARTIAL and partial is None:
                partial = route
                partial_scope = child_scope

        if partial is not None:
            scope["route"] = partial
            scope.update(partial_scope)
            await partial.handle(scope, receive, send)
            return

        route_path = get_route_path(scope)
        if scope["type"] == "http" and self.redirect_slashes and route_path != "/":
            redirect_scope: dict[str, Any] = dict(scope)
            if route_path.endswith("/"):
                redirect_scope["path"] = redirect_scope["path"].rstrip("/")
            else:
                redirect_scope["path"] = redirect_scope["path"] + "/"

            for route in self.routes:
                match, child_scope = route.matches(redirect_scope)
                if match != Match.NONE:
                    redirect_url = HTTPConnection(redirect_scope).url
                    response = RedirectResponse(url=str(redirect_url))
                    await response(scope, receive, send)
                    return

        await self.default(scope, receive, send)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Router) and self.routes == other.routes

    def mount(self, path: str, app: ASGIApplication, name: str | None = None) -> None:
        route = Mount(path, app=app, name=name)
        self.routes.append(route)

    def host(self, host: str, app: ASGIApplication, name: str | None = None) -> None:
        route = Host(host, app=app, name=name)
        self.routes.append(route)

    def add_route(
        self,
        path: str,
        endpoint: Callable[[Request], Awaitable[Response] | Response],
        methods: Collection[str] | None = None,
        name: str | None = None,
        include_in_schema: bool = True,
    ) -> None:
        route = Route(
            path,
            endpoint=endpoint,
            methods=methods,
            name=name,
            include_in_schema=include_in_schema,
        )
        self.routes.append(route)

    def add_websocket_route(
        self,
        path: str,
        endpoint: Callable[[WebSocket], Awaitable[None]],
        name: str | None = None,
    ) -> None:
        route = WebSocketRoute(path, endpoint=endpoint, name=name)
        self.routes.append(route)
