from abc import ABC, abstractmethod
from collections.abc import Sequence

from speedy.types import BaseScope, Receive, Send


class BaseRoute[ScopeT: BaseScope](ABC):
    """Base Route class."""

    @abstractmethod
    async def handle(
        self,
        scope: ScopeT,
        receive: Receive,
        send: Send,
    ) -> None:
        """ASGI App of the route."""


class Router:
    def __init__(
        self,
        route_handlers: Sequence[BaseRoute],
    ) -> None:
        self.route_handlers = tuple(route_handlers)

    def register(self, value: BaseRoute) -> None:
        if value in self:
            # TODO: change exception
            raise ValueError("Cannot register a router on itself")
        self.route_handlers = (*self.route_handlers, value)
