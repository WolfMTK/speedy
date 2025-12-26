from typing import Any


class SpeedyException(Exception):
    """ Base exception class. """

    detail: str

    def __init__(self, *args: Any, detail: str = "") -> None:
        str_args = [str(args) for arg in args if arg]
        if not detail:
            if str_args:
                detail, *str_args = str_args
            elif hasattr(self, "detail"):
                detail = self.detail
        self.detail = detail
        super().__init__(*str_args)


class ASGIApplicationException(Exception):
    pass


class ConnectionException(Exception):
    pass


class ValidationException(Exception):
    pass


class SerializationException(Exception):
    pass


class SpeedyWarning(UserWarning):
    """ Base class for Speedy warnings. """
