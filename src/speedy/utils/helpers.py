import functools
from typing import TypeVar, cast

T = TypeVar('T')


def unwrap_partial(value: T) -> T:
    """ Unwraps a partial, returning the underlying callable. """

    # INFO: Bypassing cyclical imports
    from .sync import AsyncCallable

    return cast(
        'T', value.func if isinstance(
            value, (functools.partial, AsyncCallable)
        ) else value
    )
