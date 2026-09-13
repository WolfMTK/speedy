import http.client
from collections.abc import Mapping

from speedy.status import WS_1000_NORMAL_CLOSURE


class ApplicationException(Exception):
    """Base exception."""


class StateException(ApplicationException):
    """State exception."""


class ValidationException(ApplicationException):
    """Validation exception."""


class ClientDisconnect(ApplicationException):
    """Client disconnect."""


class WebSocketDisconnected(RuntimeError):
    """Raised when attempting to use a disconnected WebSocket."""


class WebSocketDisconnect(ApplicationException):
    """Raised when the client disconnects from a WebSocket."""

    def __init__(self, code: int = WS_1000_NORMAL_CLOSURE, reason: str | None = None) -> None:
        self.code = code
        self.reason = reason or ""


class AuthenticationError(ApplicationException):
    """Raised when credentials are invalid."""


class HTTPException(ApplicationException):
    """An HTTP error carrying a status code, detail message, and optional headers."""

    def __init__(
        self,
        status_code: int,
        detail: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if detail is None:
            detail = http.client.responses.get(status_code, "")
        self.status_code = status_code
        self.detail = detail
        self.headers = headers

    def __str__(self) -> str:
        return f"{self.status_code}: {self.detail}"

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}(status_code={self.status_code!r}, detail={self.detail!r})"
