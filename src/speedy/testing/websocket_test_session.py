from __future__ import annotations

import contextlib
import math
from typing import Any, TYPE_CHECKING

import anyio.abc
from anyio.streams.stapled import StapledObjectStream

from speedy.types import WebSocketScope, ASGIApp

if TYPE_CHECKING:
    from speedy.testing.client.sync_client import TestClient


class WebSocketTestSession:
    def __init__(
            self,
            client: TestClient[Any],
            scope: WebSocketScope,
            portal: anyio.abc.BlockingPortal,
            connect_timeout: float | None = None,
    ) -> None:
        self._exit_stack = contextlib.ExitStack()
        self._portal = portal
        self._Client = client
        self._scope = scope
        self._connect_timeout = connect_timeout


class AsyncWebSocketTestSession:
    def __init__(
            self,
            *,
            app: ASGIApp,
            scope: WebSocketScope,
            connect_timeout: float | None = None,
            tg: anyio.abc.TaskGroup,
    ) -> None:
        self.scope = scope
        self.accepted_subprotocol: str | None = None
        self.extra_headers: list[tuple[bytes, bytes]] = []
        self.app = app

        self._tg = tg
        self._send_stream = StapledObjectStream(
            *anyio.create_memory_object_stream["WebSocketSendMessage"](math.inf),
        )
        self._receive_stream = StapledObjectStream(
            *anyio.create_memory_object_stream["WebSocketReceiveMessage"](math.inf),
        )
        self._exit_stack = contextlib.AsyncExitStack()
        self._connect_timeout = connect_timeout
