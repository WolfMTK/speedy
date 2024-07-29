from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from http.cookies import SimpleCookie
from typing import Any

from speedy.types import SAMESITE


@dataclass
class Cookie:
    """ Container class for defining a cookie. """

    key: str
    value: str | None = field(default=None)
    max_age: int | None = field(default=None)
    expires: datetime | str | int | None = field(default=None)
    path: str | None = field(default=None)
    domain: str | None = field(default=None)
    secure: bool = field(default=False)
    httponly: bool = field(default=False)
    samesite: SAMESITE = field(default='lax')

    def __hash__(self):
        return hash((self.key, self.path, self.domain))

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Cookie):
            return other.key == self.key and other.path == self.path and other.domain == self.domain
        return False

    @property
    def simple_cookie(self) -> SimpleCookie:
        """ Get a simple cookie object from the values. """
        simple_cookie = SimpleCookie()
        simple_cookie[self.key] = self.value or ''

        namespace = simple_cookie[self.key]
        for key, value in self.dict.items():
            if key in {'key', 'value'}:
                continue
            if value is not None:
                namespace[key] = value
        return simple_cookie

    @property
    def dict(self) -> dict[str, Any]:
        """ Get the cookie as a dict. """
        data = {}
        for key, value in asdict(self).items():
            if key == 'path' and value is None:
                data[key] = '/'
                continue
            if key == 'max_age':
                data['max-age'] = value
                continue
            data[key] = value
        return data

    def to_header(self, **kwargs: Any) -> str:
        """ Return a string representation suitable to be sent as HTTP headers. """
        return self.simple_cookie.output(**kwargs).strip()

    def to_encoded_header(self) -> tuple[bytes, bytes]:
        """ Create encoded header for send a scope. """
        return b'set-cookie', self.to_header(header='').encode('latin-1')
