from __future__ import annotations

import contextlib
from typing import Any, TYPE_CHECKING

import anyio.abc

from speedy.types import WebSocketScope

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
