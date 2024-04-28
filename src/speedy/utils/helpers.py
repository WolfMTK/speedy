from typing import TypeVar, cast
import functools
from .sync import AsyncCallable

T = TypeVar('T')


def unwrap_partial(value: T | functools.partial) -> T:
    """ Unwraps a partial, returning the underlying callable. """
    return cast(
        'T',
        value.func if isinstance(
            value,
            (functools.partial, AsyncCallable)
        ) else value
    )
