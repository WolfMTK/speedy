from speedy.exceptions.base import SpeedyException


class HTTPException(SpeedyException):
    """ Base exception for HTTP error responses. """


class ImproperlyConfiguredException(HTTPException, ValueError):
    """Application has improper configuration."""
