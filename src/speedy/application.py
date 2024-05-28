from speedy.protocols.application import ASGIApplication
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable
from speedy.types.application import ASGIAppType


class Speedy(ASGIApplication):
    def __init__(self) -> None:
        self.middleware_stack: ASGIAppType | None = None

    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        scope['app'] = self

        if self.middleware_stack is None:
            self.middleware_stack = self.build_middleware_stack()

        await self.middleware_stack(scope, receive, send)

    def build_middleware_stack(self) -> ASGIAppType:
        return self
