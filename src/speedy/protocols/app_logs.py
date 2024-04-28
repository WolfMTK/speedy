from typing import Protocol, Any


class BaseLogger(Protocol):
    """ Base Logger protocol. """

    def setLevel(self, level: int) -> None:
        """ Set the logging level. """

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `DEBUG` level. """

    def info(self, msg: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `INFO` level. """

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `WARNING` level. """

    def warn(self, msg: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `WARN` level. """

    def error(self, msg: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `ERROR` level. """

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `EXCEPTION` level. """

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `CRITICAL` level. """

    def fatal(self, msg: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `FATAL` level. """
