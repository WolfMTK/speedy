from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable, ParamSpec

from speedy.protocols import ASGIApplication
from speedy.types import ASGISendCallable, ASGIReceiveCallable, Scope

P = ParamSpec('P')


@runtime_checkable
class MiddlewareProtocol(Protocol[P]):
    def __init__(self, app: ASGIApplication, *args: P.args, **kwargs: P.kwargs) -> None: ...

    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None: ...


class AbstractMiddleware(ABC):
    @abstractmethod
    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None: ...

    # TODO: add arguments and typing
    @abstractmethod
    async def dispatch(self): ...
