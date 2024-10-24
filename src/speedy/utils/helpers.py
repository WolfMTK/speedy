import functools
import inspect
import re
from collections.abc import Callable
from typing import TypeVar, cast, Any

from speedy.types import Scope

T = TypeVar('T')


def unwrap_partial(value: T) -> T:
    """ Unwraps a partial, returning the underlying callable. """

    # INFO: Bypassing cyclical imports
    from speedy.utils.sync import AsyncCallable

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


def get_endpoint_name(endpoint: Callable[..., Any]) -> str:
    """ Get endpoint name. """
    if inspect.iscoroutine(endpoint) or inspect.isclass(endpoint):
        return endpoint.__name__
    return endpoint.__class__.__name__
