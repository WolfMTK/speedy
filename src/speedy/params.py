from dataclasses import dataclass, field, asdict
from typing import Any, Hashable

from speedy.types import Empty


@dataclass(frozen=True)
class ParameterKwarg:
    """ Data container representing a parameter. """
    annotation: Any = field(default=Empty)
    header: str | None = field(default=None)
    cookie: str | None = field(default=None)
    query: str | None = field(default=None)
    required: bool | None = field(default=None)

    def __hash__(self) -> int:
        return sum(hash(val) for val in asdict(self) if isinstance(val, Hashable))
