from typing import Protocol

from speedy.types import ASGIAppType, Receive, Scope, Send


class MiddlewareProtocol(Protocol):
    """Abstract middleware protocol."""

    app: ASGIAppType

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None: ...
