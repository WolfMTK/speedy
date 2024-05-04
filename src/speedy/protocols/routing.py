from abc import ABC, abstractmethod
from typing import Any

from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable


class AbstractRoute(ABC):
    """ Base route class. """

    # @abstractmethod
    # def match(self, scope: Scope) -> tuple[Match, Scope]: ...

    @abstractmethod
    def url_path_for(self, name: str, /, **path_params: Any) -> None: ...

    @abstractmethod
    async def handle(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable,
            send: ASGISendCallable
    ) -> None: ...
