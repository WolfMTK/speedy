from speedy.middleware._internal.exceptions import ExceptionHandlerMiddleware
from speedy.types import ASGIAppType


def wrap_in_exception_handler(app: ASGIAppType) -> ASGIAppType:
    """ Wrap the given ASGI application in an instance of ExceptionHandlerMiddleware """
    return ExceptionHandlerMiddleware(app=app)
