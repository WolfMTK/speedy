from typing import Protocol, ParamSpec
from speedy.types import (
    Scope,
    ASGIReceiveCallable,
    ASGISendCallable,
    ASGIApplication,
)

P = ParamSpec('P')


class BaseMiddleware(Protocol[P]):
    """ Abstract middleware protocol. """

    __slots__ = ('app', 'args', 'kwargs')

    def __init__(
            self,
            app: ASGIApplication,
            *args: P.args,
            **kwargs: P.kwargs
    ) -> None: ...

    async def __call__(
            self, scope: Scope,
            receive: ASGIReceiveCallable,
            send: ASGISendCallable
    ) -> None: ...
