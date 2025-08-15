from enum import Enum
from typing import Final


class _EmptyEnum(Enum):
    """A sentinel enum used as placeholder."""

    EMPTY = 0


Empty: Final = _EmptyEnum.EMPTY
