from .base import ASGIApplicationException


class HTTPException(ASGIApplicationException):
    """ Base exception for HTTP error responses. """


class InternalServerException(HTTPException):
    """ The server was unable to fulfill the request. """
