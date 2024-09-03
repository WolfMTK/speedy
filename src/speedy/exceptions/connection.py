from speedy.exceptions.base import ConnectionException


class SessionException(ConnectionException):
    pass


class AuthException(ConnectionException):
    pass


class RequestException(ConnectionException):
    pass


class InternalServerException(ConnectionException):
    pass


class WebSocketException(ConnectionException):
    pass


class WebSocketDisconnect(WebSocketException):
    pass
