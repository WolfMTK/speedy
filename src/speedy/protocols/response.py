from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class AbstractResponse(ABC):
    @abstractmethod
    def render(self, content: Any) -> bytes: ...

    @abstractmethod
    def set_cookie(
            self,
            key: str,
            value: str,
            max_age: int | None,
            expires: datetime | str | int | None,
            path: str,
            secure: bool,
            httponly: bool,
            samesite: str
    ) -> None: ...

    @abstractmethod
    def delete_cookie(
            self,
            key: str,
            path: str,
            domain: str | None,
            secure: bool,
            httponly: bool,
            samesite: str
    ) -> None: ...

    @abstractmethod
    def set_headers(self, key: str, value: str) -> None: ...

    @property
    @abstractmethod
    def headers(self) -> dict[str, Any]: ...
