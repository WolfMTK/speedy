from typing import Any, Sequence, Mapping

import httpx
from httpx import USE_CLIENT_DEFAULT
from httpx._client import UseClientDefault
from httpx._types import (
    QueryParamTypes,
    HeaderTypes,
    CookieTypes,
    TimeoutTypes
)

from speedy import ScopeType
from speedy.connection.base import ASGIConnection
from speedy.datastructures import MutableHeaders
from speedy.status_code import HTTP_200_OK
from speedy.types import HTTPResponseStartEvent, ASGIAppType, HttpScope
from speedy.utils.scope.state import ScopeState


def fake_http_send_message(headers: MutableHeaders) -> HTTPResponseStartEvent:
    headers.setdefault("content-type", "application/text")
    return HTTPResponseStartEvent(
        type="http.response.start",
        status=HTTP_200_OK,
        headers=headers.raw,
    )


def fake_asgi_connection(app: ASGIAppType, cookies: dict[str, str]) -> ASGIConnection[Any, Any, Any, Any]:
    scope: HttpScope = {
        "type": ScopeType.HTTP,
        "path": "/",
        "raw_path": b"/",
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "headers": [],
        "method": "GET",
        "http_version": "1.1",
        "extensions": {"http.response.template": {}},
        "app": app,
        "state": {},
        "path_params": {},
        "asgi": {"version": "3.0", "spec_version": "2.1"},
    }
    ScopeState.from_scope(scope).cookies = cookies
    return ASGIConnection[Any, Any, Any, Any](scope=scope)


def _prepare_ws_connect_request(
        client: httpx.Client | httpx.AsyncClient,
        url: str,
        subprotocols: Sequence[str] | None = None,
        params: QueryParamTypes | None = None,
        headers: HeaderTypes | None = None,
        cookies: CookieTypes | None = None,
        timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
        extensions: Mapping[str, Any] | None = None,
) -> httpx.Request:
    default_headers: dict[str, str] = {}
    default_headers.setdefault("connection", "upgrade")
    default_headers.setdefault("sec-websocket-key", "testserver==")
    default_headers.setdefault("sec-websocket-version", "13")
    if subprotocols is not None:
        default_headers.setdefault("sec-websocket-protocol", ", ".join(subprotocols))
    return client.build_request(
        "GET",
        client.base_url.copy_with(scheme="ws").join(url),
        headers={**dict(headers or {}), **default_headers},  # type: ignore[misc]
        params=params,
        cookies=cookies,
        extensions=None if extensions is None else dict(extensions),
        timeout=timeout,
    )
