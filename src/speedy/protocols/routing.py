from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from speedy.types import Scope


class Match(int, Enum):
    NONE = 0
    PARTIAL = 1
    FULL = 2


class BaseRoute(ABC):
    @abstractmethod
    def matches(self, scope: Scope) -> tuple[Match, Scope]: ...

    @abstractmethod
    def url_path_for(self, name: str, /, **path_params: Any): ...
