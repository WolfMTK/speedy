class ApplicationException(Exception):
    """Base exception."""


class StateException(ApplicationException):
    """State exception."""


class ValidationException(ApplicationException):
    """Validation exception."""
