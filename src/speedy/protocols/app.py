from abc import ABC, abstractmethod
from typing import Any

from speedy.datastructures import URLPath
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

    @abstractmethod
    def route_reverse(self, name: str, **path_params: Any) -> 'URLPath': ...
