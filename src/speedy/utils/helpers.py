import functools
import re
from collections.abc import Callable
from typing import TypeVar, cast, Any

from speedy.types import Scope

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


def get_route_path(scope: Scope) -> str:
    """ Get route path. """
    root_path = scope.get('root_path', '')
    root_path = re.sub(r'^' + root_path, '', scope['path'])
    return root_path
