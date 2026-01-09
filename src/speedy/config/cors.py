from dataclasses import dataclass, field
from typing import Final, Literal

from speedy.types import Method

_TTL_MAX_AGE: Final = 600


@dataclass(slots=True)
class CORSConfig:
    """Configuration for Cross-Origin Resource Sharing."""

    allow_origins: list[str] = field(default_factory=lambda: ["*"])
    allow_methods: list[Literal["*"] | Method] = field(default_factory=lambda: ["*"])
    allow_headers: list[str] = field(default_factory=lambda: ["*"])
    allow_credentials: bool = field(default=False)
    expose_headers: list[str] = field(default_factory=list)
    max_age: int = field(default=_TTL_MAX_AGE)

    def __post_init__(self) -> None:
        self.allow_headers = [val.lower() for val in self.allow_headers]
