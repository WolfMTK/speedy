from speedy.enums import ScopeType
from speedy.protocols.middleware import AbstractMiddleware
from speedy.types import Scope, Receive, Send
from speedy.types.application import ASGIAppType


class ServerErrorMiddleware(AbstractMiddleware):
    def __init__(self, app: ASGIAppType) -> None:
        self.app = app
        self.started_response = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != ScopeType.HTTP:
            await self.app(scope, receive, send)
            return None

