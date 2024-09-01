from speedy.exceptions.base import ConnectionException


class SessionException(ConnectionException):
    pass


class AuthException(ConnectionException):
    pass
