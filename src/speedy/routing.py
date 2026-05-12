from abc import ABC
from typing import TypeVar, Generic

from speedy.types import Receive, Send, BaseScope

ScopeT = TypeVar("ScopeT", bound=BaseScope)


class BaseRoute(ABC, Generic[ScopeT]):
    """Base Route class."""

    async def handle(
            self,
            scope: ScopeT,
            receive: Receive,
            send: Send,
    ) -> None:
        """ASGI App of the route."""
        raise NotImplementedError(
            "Route subclasses must implement handle "
            "which serves as the ASGI app entry point",
        )
