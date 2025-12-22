from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable, ParamSpec

from speedy.protocols.app import ASGIApplication
from speedy.types import Send, Receive, Scope

P = ParamSpec('P')


@runtime_checkable
class MiddlewareProtocol(Protocol[P]):
    def __init__(self, app: ASGIApplication, *args: P.args, **kwargs: P.kwargs) -> None: ...

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None: ...


class AbstractMiddleware(ABC):
    @abstractmethod
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None: ...

    # TODO: add arguments and typing
    @abstractmethod
    async def dispatch(self): ...
