from typing import Callable, Any

from speedy.concurrence import sync_to_thread
from speedy.constants import HTTP_METHODS
from speedy.enums import ScopeType
from speedy.exceptions import HTTPException
from speedy.protocols import BaseHTTPEndpoint, AbstractResponse
from speedy.requests import Request
from speedy.response import PlainTextResponse
from speedy.status_code import HTTP_405_METHOD_NOT_ALLOWED
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable
from speedy.utils import is_async_callable


class HTTPEndpoint(BaseHTTPEndpoint):
    def __init__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable,
            send: ASGISendCallable
    ) -> None:
        assert scope['type'] == ScopeType.HTTP

        self.scope = scope
        self.receive = receive
        self.send = send

    async def dispatch(self) -> None:
        request = Request(scope=self.scope, receive=self.receive)
        handler_name = self._get_name_handler(request)
        handler: Callable[[Request], Any] = getattr(self, handler_name, self.method_not_allowed)
        is_async = is_async_callable(handler)
        if is_async:
            response = await handler(request)
        else:
            response = await sync_to_thread(handler, request)
        await response(self.scope, self.receive, self.send)

    async def method_not_allowed(self, request: Request) -> AbstractResponse:
        headers = {
            'Allow': ', '.join(self._get_allowed_methods())
        }
        if 'app' in self.scope:
            raise HTTPException(status_code=HTTP_405_METHOD_NOT_ALLOWED, headers=headers)
        return PlainTextResponse(
            'Method not allowed',
            status_code=HTTP_405_METHOD_NOT_ALLOWED,
            headers=headers
        )

    def _get_name_handler(self, request: Request) -> str:
        if request.method == 'HEAD' and not hasattr(self, 'head'):
            return 'get'
        return request.method.lower()

    def _get_allowed_methods(self):
        for method in HTTP_METHODS:
            if getattr(self, method.lower(), None) is not None:
                yield method
