from typing import Callable, Awaitable, TypeAlias

from .asgi_types import Scope, ASGIReceiveCallable, ASGISendCallable

ASGIApplication: TypeAlias = Callable[
    [Scope, ASGIReceiveCallable, ASGISendCallable], Awaitable[None]
]
