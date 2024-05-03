from abc import ABC, abstractmethod

from speedy.types import ASGIReceiveCallable


class AbstractRequest(ABC):
    @property
    @abstractmethod
    def method(self) -> str: ...

    @property
    @abstractmethod
    def receive(self) -> ASGIReceiveCallable: ...
