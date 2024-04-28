from typing import Callable, Awaitable

from .asgi_types import Scope, ASGIReceiveCallable, ASGISendCallable

ASGIAppType = Callable[[Scope, ASGIReceiveCallable, ASGISendCallable], Awaitable[None]]
