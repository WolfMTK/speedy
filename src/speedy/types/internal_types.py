from typing import TYPE_CHECKING, Callable, Any, TypeAlias

if TYPE_CHECKING:
    from speedy.handlers.http_handlers.base import HTTPRouteHandler
    from speedy.handlers.websocket_handlers.base import WebsocketRouteHandler

RouteHandlerType: TypeAlias = "HTTPRouteHandler | WebsocketRouteHandler"

RouterHandler: TypeAlias = "RouteHandlerType | Callable[..., Any]"
