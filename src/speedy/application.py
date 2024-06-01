from typing import Sequence

from speedy.middleware import Middleware
from speedy.protocols.application import ASGIApplication
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable
from speedy.types.application import ASGIAppType
from speedy.types.asgi_types import LifespanScope, LifeSpanReceiveMessage, LifeSpanSendMessage


class Speedy(ASGIApplication):
    def __init__(self, middleware: Sequence[Middleware] | None = None) -> None:
        self.middleware_stack: ASGIAppType | None = None
        self.user_middleware = self._get_user_middleware(middleware)

    async def __call__(
            self,
            scope: Scope | LifespanScope,
            receive: ASGIReceiveCallable | LifeSpanReceiveMessage,
            send: ASGISendCallable | LifeSpanSendMessage
    ) -> None:
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
