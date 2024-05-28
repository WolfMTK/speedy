from speedy.enums import ScopeType
from speedy.protocols.middleware import BaseMiddleware
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable, Message
from speedy.types.application import ASGIAppType


class ServerErrorMiddleware(BaseMiddleware):
    def __init__(self, app: ASGIAppType) -> None:
        self.app = app
        self.started_response = False

    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        if scope['type'] != ScopeType.HTTP:
            await self.app(scope, receive, send)
            return None

        async def _send(message: Message) -> None:
            nonlocal send

            if message['type'] == 'http.response.start':
                self.started_response = True
            await send(message)  # type: ignore[arg-type]
