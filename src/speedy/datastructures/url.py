from typing import Any, Self, Sequence
from urllib.parse import urlsplit, urlencode

from speedy.types import Scope


class URL:
    def __init__(
            self,
            url: str = '',
            scope: Scope | None = None,
            **components: Any
    ) -> None:
        self._url = self._get_url(url, scope) or url

    @property
    def components(self):
        if not hasattr(self, '_components'):
            self._components = urlsplit(self._url)
        return self._components

    @property
    def scheme(self) -> str:
        return self.components.scheme

    @property
    def netloc(self) -> str:
        return self.components.netloc

    @property
    def path(self) -> str:
        return self.components.netloc

    @property
    def query(self) -> str:
        return self.components.query

    @property
    def fragment(self) -> str:
        return self.components.fragment

    @property
    def username(self) -> None | str:
        return self.components.username

    @property
    def password(self) -> None | str:
        return self.components.password

    @property
    def hostname(self) -> None | str:
        return self.components.hostname

    @property
    def port(self) -> int | None:
        return self.components.port

    @property
    def is_secure(self) -> bool:
        return self.scheme in ('https', 'wss')

    def replace(self, **kwargs: Any) -> Self:
        if (
                'username' in kwargs or
                'password' in kwargs or
                'port' in kwargs
        ):
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

                kwargs['netloc'] = netloc

        components = self.components._replace(**kwargs)
        return self.__class__(components.geturl())

    def include_query_params(self, **kwargs: Any) -> Self:
        ...

    def replace_query_params(self, **kwargs: Any) -> Self:
        query = urlencode(
            [
                (str(key), str(value)) for key, value in kwargs.items()
            ]
        )
        return self.replace(query=query)

    def remove_query_params(self, keys: str | Sequence[str]) -> Self:
        ...

    def _get_url(self,
                 url: str,
                 scope: Scope | None = None,
                 **components: Any) -> str:
        if scope is not None:
            assert not url, 'Cannot set both "url" and "scope".'
            assert not components, ('Cannot set both "scope" '
                                    'and "**components".')
            scheme = scope.get('scheme', 'http')
            server = scope.get('server', None)
            path = scope['path']
            query_string = scope.get('query_string', b'')
            host_header = self._get_host_header(scope)
            url = self._is_url(path, host_header, server, scheme)

            if query_string:
                url += '?' + query_string.decode()
            return url
        elif components:
            assert not url, 'Cannot set both "url" and "**components".'
            url = URL('').replace(**components).components.geturl()

    def _is_url(self,
                path: str,
                host_header: str | None,
                server: tuple[str, int] | None,
                scheme: str) -> str:
        if host_header is not None:
            return f'{scheme}://{host_header}{path}'
        elif server is None:
            return path
        host, port = server
        default_port = {'http': 80,
                        'https': 443,
                        'ws': 80,
                        'wss': 443}[scheme]
        if port == default_port:
            return f'{scheme}://{host}{path}'
        return f'{scheme}://{host}:{port}{path}'

    def _get_host_header(self, scope: Scope) -> str | None:
        for key, value in scope['headers']:
            if key == b'host':
                return value.decode('latin-1')

    def __eq__(self, other: Any) -> bool:
        return str(self) == str(other)

    def __str__(self) -> str:
        return self._url

    def __repr__(self) -> str:
        url = str(self)
        if self.password:
            url = str(self.replace(password='********'))
        return f'{self.__class__.__name__}({repr(url)})'


class URLPath(str):
    __slots__ = ('path', 'protocol', 'host')

    def __new__(cls,
                path: str,
                protocol: str = '',
                host: str = '') -> str:
        assert protocol in ('http', 'websocket', '')
        return str.__new__(cls, path)

    def __init__(self,
                 path: str,
                 protocol: str = '',
                 host: str = '') -> None:
        self.path = path
        self.protocol = protocol
        self.host = host

    def make_absolute_url(self, base_url: str | URL) -> URL:
        if isinstance(base_url, str):
            base_url = URL(base_url)
        if self.protocol:
            scheme = {
                'http': {
                    True: 'https',
                    False: 'http'
                },
                'websocket': {
                    True: 'wss',
                    False: 'ws'
                }
            }[self.protocol][base_url.is_secure]
        else:
            scheme = base_url.scheme

        netloc = self.host or base_url.netloc
        path = base_url.path.rstrip('/') + str(self)
        return URL(scheme=scheme, netloc=netloc, path=path)
