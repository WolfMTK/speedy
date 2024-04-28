from speedy.concurrence import sync_to_thread
from speedy.enums import ScopeType
from speedy.protocols import BaseHTTPEndpoint
from speedy.requests import Request
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
        handler = getattr(self, handler_name, self.method_not_allowed())
        is_async = is_async_callable(handler)
        if is_async:
            response = await handler(request)
        else:
            response = await sync_to_thread(handler, request)
        await response(self.scope, self.receive, self.send)

    def _get_name_handler(self, request: Request) -> str:
        if request.method == 'HEAD' and not hasattr(self, 'head'):
            return 'get'
        return request.method.lower()
