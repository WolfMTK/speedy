from abc import ABC, abstractmethod

from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable
from speedy.types.application import ASGIAppType


class ASGIApplication(ABC):
    @abstractmethod
    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None: ...

    @abstractmethod
    def build_middleware_stack(self) -> ASGIAppType: ...
