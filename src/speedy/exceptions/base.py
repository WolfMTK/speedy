class SpeedyException(Exception):
    pass


class ASGIApplicationException(Exception):
    pass


class ConnectionException(Exception):
    pass


class ValidationException(Exception):
    pass


class SerializationException(SpeedyException):
    pass


class SpeedyWarning(UserWarning):
    """ Base class for Speedy warnings. """
