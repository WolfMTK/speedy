from typing import Callable, Awaitable, Literal

from .asgi_types import (
    Scope,
    LifespanScope,
    Receive,
    Send,
    LifeSpanReceiveMessage,
    LifeSpanSendMessage,
)

ASGIAppType = Callable[[Scope | LifespanScope,
                        Receive | LifeSpanReceiveMessage,
                        Send | LifeSpanSendMessage], Awaitable[None]]
SAMESITE = Literal["lax", "strict", "none"]
