from collections.abc import Iterator
from typing import Any, Protocol

from speedy.types import ASGIApplication


class _AbstractMiddleware[**P](Protocol[P]):
    def __call__(self, app: ASGIApplication, /, *args: P.args, **kwargs: P.kwargs) -> ASGIApplication: ...


class Middleware[**P]:
    """Base middleware class."""

    def __init__(self, cls: _AbstractMiddleware[P], *args: P.args, **kwargs: P.kwargs) -> None:
        self.cls = cls
        self.args = args
        self.kwargs = kwargs

    def __iter__(self) -> Iterator[Any]:
        as_tuple = (self.cls, self.args, self.kwargs)
        return iter(as_tuple)

    def __repr__(self) -> str:
        class_name = type(self).__name__
        args_strings = (f"{value!r}" for value in self.args)
        option_strings = (f"{key}={value!r}" for key, value in self.kwargs.items())
        name = getattr(self.cls, "__name__", "")
        args_repr = ", ".join([name, *args_strings, *option_strings])
        return f"{class_name}({args_repr})"
