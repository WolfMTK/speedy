import sys
from dataclasses import dataclass
from functools import lru_cache
from typing import NamedTuple, Any, Sequence
from urllib.parse import SplitResult, urlsplit, urlunsplit, urlencode

from speedy._parsers import parse_query_string
from speedy.types.asgi_types import Scope
from .multi_dicts import MultiDict, ImmutableMultiDict

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class Address(NamedTuple):
    """ Just a network address. """

    host: str
    port: int


_DEFAULT_SCHEMA_PORTS = {'http': 80, 'https': 443, 'ws': 80, 'wss': 443}


@dataclass(unsafe_hash=True)
class URLComponents:
    """ Components in the URL. """

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
        url = self._url
        if self.password is not None:
            url = self.replace(password='**********')._url
        return f'{type(self).__name__}({url!r})'

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

        if host_header is not None:
            url = f'{scheme}://{host_header}{path}'
        elif server is None:
            url = path
        else:
            host, port = server
            default_port = _DEFAULT_SCHEMA_PORTS[scheme]
            if port == default_port:
                url = f'{scheme}://{host}{path}'
            else:
                url = f'{scheme}://{host}:{port}{path}'

        if query_string:
            url += '?' + query_string.decode()
        return cls(url)

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

    def replace_query_params(self, **kwargs: Any) -> Self:
        """ Replace query parameters in the URL. """
        query = urlencode(tuple((str(key), str(value)) for key, value in kwargs.items()))
        return self._replace_query(query)

    def include_query_params(self, **kwargs: Any) -> Self:
        """ Include query parameters in the URL. """
        query_params = MultiDict(parse_query_string(query=self.query.encode()))
        query_params.update({str(key): str(value) for key, value in kwargs.items()})
        query = urlencode(list(query_params.multi_items()))
        return self._replace_query(query)

    def remove_query_params(self, keys: str | Sequence[str]) -> Self:
        """ Remove query parameters in the URL. """
        if isinstance(keys, str):
            keys = [keys]
        query_params = MultiDict(parse_query_string(query=self.query.encode()))
        for key in keys:
            query_params.pop(key, None)
        query = urlencode(list(query_params.multi_items()))
        return self._replace_query(query)

    def replace(self, **kwargs: Any) -> Self:
        """ Replace components in the URL. """
        url_components = URLComponents(**kwargs)
        netloc = self._get_netloc(**kwargs)
        if netloc != '':
            url_components.netloc = netloc
            kwargs['netloc'] = netloc
        for key, value in vars(self.url_components).items():
            if key in kwargs:
                continue
            setattr(url_components, key, value)
        return type(self)._new(
            SplitResult(
                scheme=url_components.scheme,
                netloc=url_components.netloc,
                path=url_components.path,
                fragment=url_components.fragment,
                query=url_components.query
            )
        )

    def _get_netloc(self, **kwargs: Any) -> str:
        netloc = ''
        if ('username' in kwargs
                or 'password' in kwargs
                or 'hostname' in kwargs
                or 'port' in kwargs):
            hostname = kwargs.pop('hostname', None)
            port = kwargs.pop('port', self.port)
            username = kwargs.pop('username', self.username)
            password = kwargs.pop('password', self.password)

            if hostname is None:
                netloc = self.netloc
                _, _, hostname = netloc.rpartition('@')
                if hostname[-1] != ']':
                    hostname = hostname.rsplit(':', 1)[0]
            netloc = hostname
            if port is not None:
                netloc += f':{port}'

            if username is not None:
                userpass = username
                if password is not None:
                    userpass += f':{password}'
                netloc = f'{userpass}@{netloc}'
        return netloc

    def _replace_query(self, query: str) -> Self:
        components = self.components._replace(query=query)
        return type(self)._new(components.geturl())


class URLPath:
    """ Create an absolute URL. """

    def __init__(self, path: str | URL, base: str | URL) -> None:
        self.path = path
        self.base = base

    def __str__(self) -> str:
        return self._make_absolute_url()

    def __repr__(self) -> str:
        path = self.path
        base = self.base
        return f'{type(self).__name__}(path={path!r}, base={base!r})'

    def _make_absolute_url(self) -> str:
        url = self.base if isinstance(self.base, URL) else URL(self.base)
        path = url.path.rstrip('/') + str(self.path)
        return str(URL.from_components(URLComponents(scheme=url.scheme, netloc=url.netloc, path=path)))


class QueryParams(ImmutableMultiDict[str, str]):
    def __init__(
            self,
            *args: ImmutableMultiDict[Any, Any] | list[tuple[Any, Any]] | str | bytes,
            **kwargs: Any
    ) -> None:
        self._check_args(*args)

        value = args[0] if args else []
        if isinstance(value, str):
            args = (parse_query_string(value),)
        elif isinstance(value, bytes):
            args = (parse_query_string(value),)
        super().__init__(*args, **kwargs)

        self._stack = [(str(key), str(value)) for key, value in self._stack]
        self._dict = {str(key): str(value) for key, value in self._dict.items()}

    def __str__(self) -> str:
        return urlencode(self._stack)

    def __repr__(self) -> str:
        return f'{type(self).__name__}({str(self)!r})'
