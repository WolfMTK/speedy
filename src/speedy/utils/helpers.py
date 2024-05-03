import functools
from typing import TypeVar, cast, Generic

from speedy.utils.sync import AsyncCallable

T = TypeVar('T')


def unwrap_partial(value: T) -> T:
    """ Unwraps a partial, returning the underlying callable. """
    return cast(
        'T', value.func if isinstance(  # type: ignore[union-attr]
            value, (functools.partial, AsyncCallable)
        ) else value
    )
