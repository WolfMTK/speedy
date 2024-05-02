from abc import ABC
from collections.abc import Iterable

from speedy.status_code import WS_1000_NORMAL_CLOSURE
from speedy.types import Message


class AbstractWebSocket(ABC):
    async def receive(self) -> Message: ...

    async def accept(
            self,
            subprotocol: str | None = None,
            headers: Iterable[tuple[bytes, bytes]] | None = None
    ) -> None: ...

    async def close(
            self,
            code: int = WS_1000_NORMAL_CLOSURE,
            reason: str | None = None
    ) -> None: ...
