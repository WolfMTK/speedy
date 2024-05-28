from typing import ParamSpec, Iterator, Any

from speedy.protocols.middleware import MiddlewareProtocol

P = ParamSpec('P')


class Middleware:
    def __init__(self, cls: type[MiddlewareProtocol[P]], *args: P.args, **kwargs: P.kwargs) -> None:
        self.cls = cls
        self.args = args
        self.kwargs = kwargs

    def __iter__(self) -> Iterator[Any]:
        return iter((self.cls, self.args, self.kwargs))
