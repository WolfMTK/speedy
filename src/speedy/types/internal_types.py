from typing import TYPE_CHECKING, Any, Callable, Literal, NamedTuple, TypeAlias

if TYPE_CHECKING:
    from speedy.handlers.asgi import ASGIRouteHandler
    from speedy.handlers.base import BaseRouteHandler
    from speedy.handlers.http_handlers.base import HTTPRouteHandler
    from speedy.handlers.websocket_handlers.base import WebsocketRouteHandler
    from speedy.types import Method

RouteHandlerType: TypeAlias = (
    "HTTPRouteHandler | WebsocketRouteHandler | ASGIRouteHandler"
)

RouterHandler: TypeAlias = "RouteHandlerType | Callable[..., Any]"

ControllerRouterHandler: TypeAlias = "RouteHandlerType | Callable[..., Any]"

RouteHanderMapItem: TypeAlias = (
    'dict[Method | Literal["websocket", "asgi"], BaseRouteHandler]'
)


class PathParameterDefinition(NamedTuple):
    """Path parameter tuple."""

    name: str
    full: str
    type: type
    parser: Callable[[str], Any] | None
