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
