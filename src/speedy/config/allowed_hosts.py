from dataclasses import field

from attr import dataclass

from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.types import Scopes


@dataclass
class AllowedHostsConfig:
    """Configuration for allowed hosts protection."""

    allowed_hosts: list[str] = field(default_factory=lambda: ["*"])
    exclude: str | list[str] | None = field(default=None)
    exclude_opt_key: str | None = field(default=None)
    scopes: Scopes | None = field(default=None)
    www_redirect: bool = field(default=True)

    def __post_init__(self) -> None:
        for host in self.allowed_hosts:
            if host != "*" and "*" in host and not host.startswith("*."):
                raise ImproperlyConfiguredException(
                    "domain wildcards can only appear in the beginning of the domain"
                )
