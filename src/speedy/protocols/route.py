from abc import ABC, abstractmethod
from typing import Any

from speedy import Match
from speedy.datastructures import URLPath
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable


class AbstractRoute(ABC):
    @abstractmethod
    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None: ...

    @abstractmethod
    def matches(self, scope: Scope) -> tuple[Scope, Match]: ...

    @abstractmethod
    def url_for_path(self, name: str, **params: Any) -> URLPath: ...

    @abstractmethod
    async def handle(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None: ...
