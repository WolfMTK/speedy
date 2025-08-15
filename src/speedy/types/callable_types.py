from collections.abc import Callable
from typing import TypeAlias, Any

Serializer: TypeAlias = Callable[[Any], Any]