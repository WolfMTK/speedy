from typing import TYPE_CHECKING, Callable, Any, TypeAlias, NamedTuple

if TYPE_CHECKING:
    from speedy.handlers.http_handlers.base import HTTPRouteHandler
    from speedy.handlers.websocket_handlers.base import WebsocketRouteHandler

RouteHandlerType: TypeAlias = "HTTPRouteHandler | WebsocketRouteHandler"

RouterHandler: TypeAlias = "RouteHandlerType | Callable[..., Any]"


class PathParameterDefinition(NamedTuple):
    """Path parameter tuple."""
    name: str
    full: str
    type: type
    parser: Callable[[str], Any] | None
