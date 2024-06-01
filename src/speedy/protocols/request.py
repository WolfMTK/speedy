from abc import ABC, abstractmethod
from typing import AsyncGenerator

from speedy.types import Method


class AbstractRequest(ABC):
    @property
    @abstractmethod
    def method(self) -> Method: ...

    @abstractmethod
    async def stream(self) -> AsyncGenerator[bytes, None]: ...

    @abstractmethod
    async def body(self) -> bytes: ...
