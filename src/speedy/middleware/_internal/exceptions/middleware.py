from typing import Any

from speedy.connection import Request
from speedy.exceptions.responses import create_exception_response
from speedy.response import Response
from speedy.types import ASGIApp, Scope, Receive, Send, Message
from speedy.utils.scope import ScopeState


class ExceptionHandlerMiddleware:
    """ Middleware used to wrap an ASGIApp inside a try catch block and handle any exceptions raised. """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope_state = ScopeState.from_scope(scope)

        async def capture_response_started(event: Message) -> None:
            if event["type"] == "http.response.start":
                scope_state.response_started = True
            await send(event)

        await self.app(scope, receive, capture_response_started)

    def default_http_exception_handler(self, request: Request, exc: Exception) -> Response[Any]:
        """ Handle an HTTP exception by returning the appropriate response. """
        return create_exception_response(request=request, exc=exc)
