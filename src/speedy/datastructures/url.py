from dataclasses import dataclass
from functools import lru_cache
from typing import NamedTuple, Self, Any
from urllib.parse import SplitResult, urlsplit, urlunsplit, urlencode

from speedy._parsers import parse_query_string
from speedy.types.asgi_types import Scope
from .multi_dicts import MultiDict


class Address(NamedTuple):
    """ Just a network address. """

    host: str
    port: int


_DEFAULT_SCHEMA_PORTS = {'http': 80, 'https': 443, 'ws': 80, 'wss': 443}


@dataclass
class URLComponents:
    scheme: str = ''
    netloc: str = ''
    path: str = ''
    fragment: str = ''
    query: str = ''
    username: str | None = None
    password: str | None = None
    port: int | None = None
    hostname: str | None = None


class URL:
    """ Representation and modification utilities of a URL. """

    _parser_url: str | None

    url_components: URLComponents

    def __new__(cls, url: str | SplitResult) -> Self:
        """ Create a new instance. """
        return cls._new(url)

    def __eq__(self, other: Any) -> bool:
        return str(self) == str(other)

    def __str__(self) -> str:
        return self._url

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self._url!r})'

    @classmethod
    def from_scope(cls, scope: Scope) -> Self:
        """ Construct a URL from a scope. """
        scheme = scope.get('scheme', 'http')
        server = scope.get('server', None)
        path = scope['path']
        query_string = scope.get('query_string', b'')

        host_header = None
        for key, value in scope['headers']:
            if key == b'host':
                host_header = value.decode('latin-1')
                break

        if server and not host_header:
            host, port = server
            default_port = _DEFAULT_SCHEMA_PORTS[scheme]
            if port != default_port:
                host_header = f'{host}:{port}'

        if not server:
            scheme = ''

        return cls.from_components(
            URLComponents(
                scheme=scheme,
                query=query_string.decode(),
                netloc=host_header,  # type: ignore[arg-type]
                path=path
            )
        )

    @classmethod
    @lru_cache
    def from_components(cls, components: URLComponents) -> Self:
        """ Create a new URL from components. """
        return cls(
            SplitResult(
                scheme=components.scheme,
                netloc=components.netloc,
                path=components.path,
                fragment=components.fragment,
                query=components.query
            )
        )

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
        instance.url_components = URLComponents(
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
    def scheme(self) -> str:
        """ scheme in the URL. """
        return self.url_components.scheme

    @property
    def hostname(self) -> str | None:
        """ hostname in the URL. """
        return self.url_components.hostname

    @property
    def port(self) -> int | None:
        """ port in the URL. """
        return self.url_components.port

    @property
    def netloc(self) -> str:
        """ netloc in the URL. """
        return self.url_components.netloc

    @property
    def username(self) -> str | None:
        """ username in the URL. """
        return self.url_components.username

    @property
    def password(self) -> str | None:
        """ password in the URL. """
        return self.url_components.password

    @property
    def path(self) -> str:
        """ path in the URL. """
        return self.url_components.path

    @property
    def query(self) -> str:
        """ query in the URL. """
        return self.url_components.query

    @property
    def fragment(self) -> str:
        """ fragment in the URL. """
        return self.url_components.fragment

    @property
    def components(self) -> SplitResult:
        """ components in the URL. """
        if not hasattr(self, '_components'):
            self._components = urlsplit(self._url)
        return self._components

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

    def replace_query(self, **kwargs: Any) -> Self:
        """ Replace the query string in the URL. """
        query = urlencode(tuple((str(key), str(value)) for key, value in kwargs.items()))
        return self._replace_query(query)

    def include_query_params(self, **kwargs: Any) -> Self:
        """ Include query parameters in the URL. """
        query_params = MultiDict(parse_query_string(query=self.query.encode()))
        query_params.update({str(key): str(value) for key, value in kwargs.items()})
        query = urlencode(list(query_params.multi_items()))
        return self._replace_query(query)

    def _replace_query(self, query: str) -> Self:
        components = self.components._replace(query=query)
        return type(self)._new(components.geturl())
