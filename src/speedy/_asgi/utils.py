from speedy.middleware._internal.exceptions import ExceptionHandlerMiddleware
from speedy.types import ASGIApp


def wrap_in_exception_handler(app: ASGIApp) -> ASGIApp:
    """ Wrap the given ASGI application in an instance of ExceptionHandlerMiddleware """
    return ExceptionHandlerMiddleware(app=app)
