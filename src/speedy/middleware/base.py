from typing import ParamSpec, Iterator, Any

from speedy.protocols.middleware import MiddlewareProtocol

P = ParamSpec('P')


class Middleware:
    """ Middleware class. """
    def __init__(self, cls: type[MiddlewareProtocol], *args: P.args, **kwargs: P.kwargs) -> None:
        self.cls = cls
        self.args = args
        self.kwargs = kwargs

    def __iter__(self) -> Iterator[Any]:
        return iter((self.cls, self.args, self.kwargs))

    def __repr__(self):
        _class = type(self).__name__
        args = ', '.join(
            [self.cls.__name__]
            + list(self._get_args_to_string())
            + list(self._get_option_to_string())
        )
        return f'{_class}({args})'

    def _get_args_to_string(self) -> Iterator[str]:
        for value in self.args:
            yield f'{value!r}'

    def _get_option_to_string(self) -> Iterator[str]:
        for key, value in self.kwargs:
            yield f'{key}={value!r}'
