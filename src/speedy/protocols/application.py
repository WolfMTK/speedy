from abc import ABC, abstractmethod

from speedy.types.asgi_types import Scope, ASGIReceiveCallable, ASGISendCallable


class ASGIApplication(ABC):
    @abstractmethod
    async def __call__(self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None: ...
