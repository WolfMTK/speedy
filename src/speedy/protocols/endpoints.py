from abc import ABC
from typing import Iterator, Any


class BaseEndpoint(ABC):
    def __await__(self) -> Iterator[Any]:
        return self.dispatch().__await__()

    async def dispatch(self) -> None: ...


class BaseHTTPEndpoint(BaseEndpoint):
    async def method_not_allowed(self): ...


class BaseWebSocketEndpoint(BaseEndpoint):
    async def decode(self) -> Any: ...

    async def on_connect(self) -> None: ...

    async def on_receive(self) -> None: ...

    async def on_disconnect(self) -> None: ...
