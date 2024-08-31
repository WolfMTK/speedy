from abc import ABC, abstractmethod

from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable
from speedy.types.application import ASGIAppType
from speedy.types.asgi_types import LifespanScope, LifeSpanReceiveMessage, LifeSpanSendMessage


class ASGIApplication(ABC):
    @abstractmethod
    async def __call__(
            self,
            scope: Scope | LifespanScope,
            receive: ASGIReceiveCallable | LifeSpanReceiveMessage,
            send: ASGISendCallable | LifeSpanSendMessage
    ) -> None: ...

    @abstractmethod
    def build_middleware_stack(self) -> ASGIAppType: ...
