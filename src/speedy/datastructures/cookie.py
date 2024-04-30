import datetime as dt
from dataclasses import dataclass, field
from typing import Literal, Any


@dataclass
class Cookie:
    """
    Container class for defining a cookie using the ``Set-Cookie`` header.

    See:
     https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie
     for more details regarding this header.
    """
    key: str
    path: str = '/'
    secure: bool = False
    httponly: bool = False
    value: str | None = field(default=None)
    max_age: int | None = field(default=None)
    expires: dt.datetime | str | int | None = field(default=None)
    domain: str | None = field(default=None)
    samesite: Literal['lax', 'strict', 'none'] = field(default='lax')

    def __hash__(self) -> int:
        return hash((self.key, self.path, self.domain))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Cookie):
            return (other.key == self.key and
                    other.path == self.path and
                    other.domain == self.domain)
        return False
