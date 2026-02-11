from __future__ import annotations

from typing import Sequence, Mapping, Any, Callable

from speedy.connection.base import ASGIConnection
from speedy.handlers.base import BaseRouteHandler
from speedy.types import AsyncAnyCallable, ExceptionHandlersMap, ParametersMap


class ASGIRouteHandler(BaseRouteHandler):
    def __init__(
            self,
            path: str | Sequence[str] | None = None,
            *,
            fn: AsyncAnyCallable,
            exception_handlers: ExceptionHandlersMap | None = None,
            name: str | None = None,
            opt: Mapping[str, Any] | None = None,
            signature_namespace: Mapping[str, Any] | None = None,
            parameters: ParametersMap | None = None,
            **kwargs: Any,
    ) -> None:
        super().__init__(
            path=path,
            fn=fn,
            exception_handlers=exception_handlers,
            name=name,
            opt=opt,
            signature_namespace=signature_namespace,
            parameters=parameters,
            **kwargs,
        )

    async def handle(self, connection: ASGIConnection[ASGIRouteHandler, Any, Any, Any]) -> None:
        """ ASGI app that authorizes the connection and then awaits the handler function """
        await self.fn(
            scope=connection.scope,
            receive=connection.receive,
            send=connection.send,
        )



# TODO: transfer the implementation to Speedy, APIRouter
def asgi(
        path: str | Sequence[str] | None = None,
        *,
        exception_handlers: ExceptionHandlersMap | None = None,
        name: str | None = None,
        handler_class: type[ASGIRouteHandler] = ASGIRouteHandler,
        **kwargs: Any,
) -> Callable[[AsyncAnyCallable], ASGIRouteHandler]:
    """ Create an ASGIRouteHandler. """

    def decorator(fn: AsyncAnyCallable) -> ASGIRouteHandler:
        return handler_class(
            fn=fn,
            path=path,
            exception_handlers=exception_handlers,
            name=name,
            **kwargs,
        )

    return decorator
