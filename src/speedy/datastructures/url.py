from dataclasses import dataclass
from functools import lru_cache
from typing import NamedTuple, Self, Any
from urllib.parse import SplitResult, urlsplit, urlunsplit


class Address(NamedTuple):
    """ Just a network address. """

    host: str
    port: int


_DEFAULT_SCHEMA_PORTS = {'http': 80, 'https': 443, 'ws': 80, 'wss': 443}


@dataclass
class _URLComponents:
    scheme: str
    netloc: str
    path: str
    fragment: str
    query: str
    username: str | None
    password: str | None
    port: int | None
    hostname: str | None


class URL:
    """ Representation and modification utilities of a URL. """

    _parser_url: str | None

    url_components: _URLComponents

    def __new__(cls, url: str | SplitResult) -> Self:
        """ Create a new instance. """
        return cls._new(url)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, (str, URL)):
            return str(self) == str(other)
        return False

    def __str__(self) -> str:
        return self._url

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self._url!r})'

    @classmethod
    @lru_cache
    def _new(cls, url: str | SplitResult) -> Self:
        instance = super().__new__(cls)
        instance._parser_url = None

        if isinstance(url, str):
            result = urlsplit(url)
            instance._parser_url = url
        else:
            result = url

        instance.url_components = _URLComponents(
            scheme=result.scheme,
            netloc=result.netloc,
            path=result.path,
            fragment=result.fragment,
            query=result.query,
            username=result.username,
            password=result.password,
            port=result.port,
            hostname=result.hostname
        )

        return instance

    @property
    def _url(self) -> str:
        if not self._parser_url:
            self._parser_url = str(
                urlunsplit(
                    SplitResult(
                        scheme=self.url_components.scheme,
                        netloc=self.url_components.netloc,
                        path=self.url_components.path,
                        fragment=self.url_components.fragment,
                        query=self.url_components.query
                    )
                )
            )
        return self._parser_url
