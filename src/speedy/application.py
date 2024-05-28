from typing import Sequence, Any

from speedy.middleware import Middleware
from speedy.protocols.application import ASGIApplication
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable
from speedy.types.application import ASGIAppType


class Speedy(ASGIApplication):
    def __init__(self, middleware: Sequence[Middleware] | None = None) -> None:
        self.middleware_stack: ASGIAppType | None = None
        self.user_middleware = self._get_user_middleware(middleware)

    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        scope['app'] = self

        if self.middleware_stack is None:
            self.middleware_stack = self.build_middleware_stack()

        await self.middleware_stack(scope, receive, send)

    def build_middleware_stack(self) -> ASGIAppType:
        return self

    def _get_user_middleware(self, middleware: Sequence[Middleware] | None) -> list[Middleware]:
        if middleware is None:
            return []
        return list(middleware)
