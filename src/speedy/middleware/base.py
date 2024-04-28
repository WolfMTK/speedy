from typing import Iterator, Any

from speedy.protocols import BaseMiddleware
from speedy.protocols.middleware import P


class Middleware:
    """ Base middleware. """

    __slots__ = ('cls', 'args', 'kwargs')

    def __init__(
            self,
            cls: type[BaseMiddleware],
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
        return f'{class_name}({self._get_args_repr()})'

    def _get_args_repr(self) -> str:
        return ', '.join(
            [
                self.cls.__name__
            ] + self._get_args_arr_string() + self._get_kwargs_arr_string()
        )

    def _get_args_arr_string(self) -> list[str]:
        return [f'{value!r}' for value in self.args]

    def _get_kwargs_arr_string(self) -> list[str]:
        return [f'{key}={value!r}' for key, value in self.kwargs.items()]
