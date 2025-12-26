from __future__ import annotations

from typing import Callable, Any, cast

import pytest

from speedy import Speedy
from speedy.types import Scope, ASGIVersion, RouteHandlerType


@pytest.fixture
def create_scope() -> Callable[..., Scope,]:
    def inner(
            *,
            type: str = "http",
            app: Speedy | None = None,
            asgi: ASGIVersion | None = None,
            http_version: str = "1.1",
            scheme: str = "http",
            path: str = "/",
            query_string: str = "",
            root_path: str = "",
            path_params: dict[str, str] | None = None,
            client: tuple[str, int] | None = ("testclient", 50000),
            server: tuple[str, int | None] | None = ("testserver", 80),
            state: dict[str, Any] | None = None,
            extensions: dict[str, dict[object, object]] | None = None,
            route_handler: RouteHandlerType | None = None,
            **kwargs: Any,
    ) -> Scope:
        scope = {
            "app": app,
            "asgi": asgi or {"spec_version": "2.0", "version": "3.0"},
            "http_version": http_version,
            "scheme": scheme,
            "path": path,
            "raw_path": path.encode(),
            "query_string": query_string.encode(),
            "root_path": root_path,
            "path_params": path_params or {},
            "headers": [],
            "client": client,
            "server": server,
            "state": state or {},
            "extensions": extensions or {"http.response.template": {}},
            "route_handler": route_handler,
            "type": type,
            "method": "GET",
            **kwargs,
        }
        return cast(Scope, scope)

    return inner


@pytest.fixture
def scope(create_scope: Callable[..., Scope]) -> Scope:
    return create_scope()
