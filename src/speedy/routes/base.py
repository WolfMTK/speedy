from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from speedy.routes.helpers import _parse_path
from speedy.types import BaseScope, Receive, Send

ScopeT = TypeVar("ScopeT", bound="BaseScope")


class BaseRoute(ABC, Generic[ScopeT]):
    """ Base route class. """

    def __init__(
            self,
            *,
            path: str,
    ) -> None:
        self.path, self.path_format, self.path_components, self.path_parameters = _parse_path(path)

    @abstractmethod
    async def handle(self, scope: ScopeT, receive: Receive, send: Send) -> None:
        """ ASGI app of the route. """
