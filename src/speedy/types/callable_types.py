from collections.abc import Callable, Awaitable
from typing import TypeAlias, Any

Serializer: TypeAlias = Callable[[Any], Any]

AsyncAnyCallable: TypeAlias = Callable[..., Awaitable[Any]]
