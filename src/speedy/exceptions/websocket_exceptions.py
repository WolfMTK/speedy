from .base import ASGIApplicationException


class WebSocketException(ASGIApplicationException):
    """ Exception class for websocket related events. """


class WebSocketDisconnect(WebSocketException):
    """ Exception class for websocket disconnect events. """
