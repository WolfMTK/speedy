from abc import ABC

from speedy.types import Receive, Send, BaseScope


class BaseRoute[ScopeT: BaseScope](ABC):
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
