from abc import abstractmethod
from typing import Protocol, Any


class ILogger(Protocol):
    """ Logger protocol. """

    @abstractmethod
    def debug(self, event: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `DEBUG` level. """

    @abstractmethod
    def info(self, event: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `INFO` level. """

    @abstractmethod
    def warning(self, event: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `WARNING` level. """

    @abstractmethod
    def warn(self, event: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `WARN` level. """

    @abstractmethod
    def error(self, event: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `ERROR` level. """

    @abstractmethod
    def fatal(self, event: str, *args: Any, **kwargs: Any) -> Any:
        """ Output a log message at `FATAL` level. """

    @abstractmethod
    def exception(self, event: str, *args: Any, **kwargs: Any) -> Any:
        """ Log a message with level `ERROR` on this logger. """

    @abstractmethod
    def critical(self, event: str, *args: Any, **kwargs: Any) -> Any:
        """.Output a log message at `INFO` level. """

    @abstractmethod
    def setLevel(self, level: int) -> None:
        """ Set the log level. """
