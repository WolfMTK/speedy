from __future__ import annotations

from speedy.enums import ScopeType
from speedy.middleware._utils import build_exclude_path_pattern
from speedy.protocols import MiddlewareProtocol
from speedy.types import ASGIAppType, Scopes


class BaseMiddleware(MiddlewareProtocol):
    """Abstract middleware providing base functionality common to all middlewares."""

    def __init__(
        self,
        app: ASGIAppType,
        exclude: str | list[str] | None = None,
        exclude_opt_key: str | None = None,
        scopes: Scopes | None = None,
    ) -> None:
        self.app = app
        self.scopes = scopes or {ScopeType.HTTP, ScopeType.WEBSOCKET}
        self.exclude_opt_key = exclude_opt_key
        self.exclude_pattern = build_exclude_path_pattern(
            exclude=exclude,
        )
