from http import HTTPStatus
from typing import Any

from speedy.exceptions.base import SpeedyException
from speedy.status_code import HTTP_500_INTERNAL_SERVER_ERROR
from speedy.types import Empty, EmptyType


class HTTPException(SpeedyException):
    """ Base exception for HTTP error responses. """

    status_code: int = HTTP_500_INTERNAL_SERVER_ERROR
    detail: str
    headers: dict[str, str] | None = None
    extra: dict[str, Any] | list[Any] | None = None

    def __init__(
            self,
            *args: Any,
            detail: str = "",
            status_code: int | None = None,
            headers: dict[str, str] | None  = None,
            extra: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        super().__init__(*args, detail=detail)
        self.status_code = status_code or self.status_code
        self.extra = extra if extra is not None else self.extra
        self.headers = headers if headers is not None else self.headers
        if not self.detail:
            self.detail = HTTPStatus(self.status_code).phrase
        self.args = (f"{self.status_code}: {self.detail}", *self.args)



class ImproperlyConfiguredException(HTTPException, ValueError):
    """Application has improper configuration."""
