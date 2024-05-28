from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable, ParamSpec

from speedy.types import ASGISendCallable, ASGIReceiveCallable, Scope

P = ParamSpec('P')


@runtime_checkable
class MiddlewareProtocol(Protocol):
    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None: ...


class BaseMiddleware(ABC):
    @abstractmethod
    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None: ...
