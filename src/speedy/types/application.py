from typing import Callable, Awaitable

from .asgi_types import (
    Scope,
    LifespanScope,
    ASGIReceiveCallable,
    ASGISendCallable,
    LifeSpanReceiveMessage,
    LifeSpanSendMessage,
)

ASGIAppType = Callable[[Scope | LifespanScope,
                        ASGIReceiveCallable | LifeSpanReceiveMessage,
                        ASGISendCallable |
                        LifeSpanSendMessage], Awaitable[None]]
