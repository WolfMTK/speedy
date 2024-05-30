from collections.abc import Iterator
from typing import Any, ParamSpec

from speedy.protocols import BaseMiddleware

P = ParamSpec('P')


class Middleware:
    """ Base middleware. """

    __slots__ = ('cls', 'args', 'kwargs')

    def __init__(
            self,
            cls: type[BaseMiddleware[P]],
            *args: P.args,
            **kwargs: P.kwargs
    ) -> None:
        self.cls = cls
        self.args = args
        self.kwargs = kwargs

    def __iter__(self) -> Iterator[Any]:
        return iter((self.cls, self.args, self.kwargs))

    def __repr__(self) -> str:
        class_name = type(self).__name__
        class_args = ', '.join(
            [self.cls.__name__]
            + list(self._get_args_arr_sting())
            + list(self._get_kwargs_arr_string())
        )
        return f'{class_name}({class_args})'

    def _get_args_arr_sting(self) -> Iterator[str]:
        for value in self.args:
            yield f'{value!r}'

    def _get_kwargs_arr_string(self) -> Iterator[str]:
        for key, value in self.kwargs.items():
            yield f'{key}={value!r}'
