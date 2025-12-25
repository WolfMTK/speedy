from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from typing import Callable, Any
from typing import NoReturn, Literal, cast

from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.protocols import ILogger
from speedy.types import ExceptionLoggingHandler, GetLogger

LOG_EXCEPTION = Literal["always", "debug", "never"]


def _get_default_formatters() -> dict[str, dict[str, Any],]:
    return {
        "standard": {
            "format": "%(levelname)s - %(asctime)s - %(name)s - %(module)s - %(message)s"
        }
    }


def _get_default_loggers() -> dict[str, dict[str, Any]]:
    return {
        "speedy": {
            "level": "INFO",
        }
    }


def get_logger_placeholder(_: str | None = None) -> NoReturn:
    """ Raise exception if logger was not set. """
    raise ImproperlyConfiguredException(
        "cannot call `.get_logger` without passing `logging_config` to the Speedy constructor first",
    )


class BaseLoggingConfig(ABC):
    """ Abstract base class for logging configuration. """
    log_exceptions: LOG_EXCEPTION
    exception_logging_handler: ExceptionLoggingHandler | None
    disable_stack_trace: set[int | type[Exception]]

    @abstractmethod
    def configure(self) -> GetLogger:
        """ Return logger with the given configuration. """

    @abstractmethod
    def set_level(self, logger: Any, level: int) -> None:
        """ Set logger level. """


@dataclass(slots=True)
class LoggingConfig(BaseLoggingConfig):
    log_exceptions: LOG_EXCEPTION = field(default="always")
    exception_logging_handler: ExceptionLoggingHandler | None = field(default=None)
    disable_stack_trace: set[int | type[Exception]] = field(default_factory=set)

    version: Literal[1] = field(default=1)
    formatters: dict[str, dict[str, Any]] = field(default_factory=_get_default_formatters)
    loggers: dict[str, dict[str, Any]] = field(default_factory=_get_default_loggers)

    def __post_init__(self) -> None:
        if "standard" not in self.formatters:
            self.formatters["standard"] = _get_default_formatters()["standard"]

        if "speedy" not in self.loggers:
            self.loggers["speedy"] = _get_default_loggers()["speedy"]

    def configure(self) -> GetLogger:
        """ Return logger with the given configuration. """
        from logging import config, getLogger

        exclude_fields = {
            "log_exceptions",
            "exception_logging_handler",
            "disable_stack_trace",
        }

        values = dict()
        for val in fields(self):
            if getattr(self, val.name) is not None and val.name not in exclude_fields:
                values[val.name] = getattr(self, val.name)

        config.dictConfig(values)
        return cast("Callable[[str], ILogger]", getLogger)

    def set_level(self, logger: ILogger, level: int) -> None:
        """ Set logger level. """
        logger.setLevel(level)
