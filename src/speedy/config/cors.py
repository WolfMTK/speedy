import re
from dataclasses import dataclass, field
from functools import cached_property
from typing import Final, Literal

from speedy.constants import DEFAULT_ALLOWED_CORS_HEADERS
from speedy.types import Method

_TTL_MAX_AGE: Final = 600


@dataclass(slots=True)
class CORSConfig:
    """Configuration for Cross-Origin Resource Sharing."""

    allow_origins: list[str] = field(default_factory=lambda: ["*"])
    allow_methods: list[Literal["*"] | Method] = field(default_factory=lambda: ["*"])
    allow_headers: list[str] = field(default_factory=lambda: ["*"])
    allow_credentials: bool = field(default=False)
    allow_origin_regex: str | None = field(default=None)
    expose_headers: list[str] = field(default_factory=list)
    max_age: int = field(default=_TTL_MAX_AGE)

    def __post_init__(self) -> None:
        self.allow_headers = [val.lower() for val in self.allow_headers]

    @cached_property
    def allowed_origings_regex(self) -> re.Pattern[str]:
        """Get or create a compiledd regex for allowed origins."""
        origins = list(self.allow_origins)
        if self.allow_origin_regex:
            origins.append(self.allow_origin_regex)
        return re.compile(
            "|".join([origin.replace("*.", r".*\.") for origin in origins])
        )

    @cached_property
    def is_allow_all_origins(self) -> bool:
        """Get a cached boolean flag dictating whether all origins are allowed."""
        return "*" in self.allow_origins

    @cached_property
    def is_allow_all_methods(self) -> bool:
        """Get a cached boolean flag dictating whether all methods are allowed."""
        return "*" in self.allow_methods

    @cached_property
    def is_allow_all_headers(self) -> bool:
        """Get a cached boolean flag dictating whether all headers are allowed."""
        return "*" in self.allow_headers

    @cached_property
    def simpe_headers(self) -> dict[str, str]:
        """Get cached simple headers."""
        simple_headers = {}
        if self.is_allow_all_origins:
            simple_headers["Access-Control-Allow-Origin"] = "*"
        if self.allow_credentials:
            simple_headers["Access-Control-Allow-Credentials"] = "true"
        if self.expose_headers:
            simple_headers["Access-Control-Expose-Headers"] = ", ".join(
                sorted(set(self.expose_headers))
            )
        return simple_headers

    @cached_property
    def preflight_headers(self) -> dict[str, str]:
        """Get cached pre-flight headers."""
        headers = {"Access-Control-Max-Age": str(self.max_age)}
        if self.is_allow_all_origins:
            headers["Access-Control-Allow-Origin"] = "*"
        else:
            headers["Vary"] = "Origin"
        if self.allow_credentials:
            headers["Access-Control-Allow-Credentials"] = str(
                self.allow_credentials
            ).lower()
        if not self.is_allow_all_headers:
            headers["Access-Control-Allow-Headers"] = ", ".join(
                sorted(set(self.allow_headers) | DEFAULT_ALLOWED_CORS_HEADERS)
            )
        if self.allow_methods:
            headers["Access-Control-Allow-Methods"] = ", ".join(
                sorted(
                    {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"}
                    if self.is_allow_all_methods
                    else set(self.allow_methods)
                )
            )
        return headers

    def is_origin_allowed(self, origin: str) -> bool:
        """Check whether a given origin is allowed."""
        return bool(
            self.is_allow_all_origins or self.allowed_origings_regex.fullmatch(origin)
        )
