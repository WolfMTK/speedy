from abc import ABC, abstractmethod
from collections.abc import Sequence

from speedy.middleware import Middleware
from speedy.types import BaseScope, Lifespan, Receive, Send


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
        routes: Sequence[BaseRoute] | None = None,
        redirect_slashes: bool = True,
        lifespan: Lifespan | None = None,
        *,
        middleware: Sequence[Middleware] | None = None,
        max_body_size: int | None = None,
    ) -> None: ...
