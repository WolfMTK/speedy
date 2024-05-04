from dataclasses import dataclass, field
from typing import Any, Self
from urllib.parse import urlsplit, SplitResult

from speedy.types import Scope


@dataclass(frozen=True)
class DefaultScheme:
    http: int = field(init=False, default=80)
    https: int = field(init=False, default=443)
    ws: int = field(init=False, default=80)
    wss: int = field(init=False, default=443)


@dataclass
class Server:
    host: str
    port: int | None = field(default=None)


@dataclass
class Netloc:
    hostname: str | None = field(default=None)
    port: int | None = field(default=None)
    username: str | None = field(default=None)
    password: str | None = field(default=None)


class URL:
    def __init__(
            self,
            url: str = '',
            scope: Scope | None = None,
            **components: Any
    ) -> None:
        self._url = self._get_url(url, scope, **components)

    @property
    def components(self) -> SplitResult:
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
        return self.components.path

    @property
    def query(self) -> str:
        return self.components.query

    @property
    def fragment(self) -> str:
        return self.components.fragment

    @property
    def username(self) -> str | None:
        return self.components.username

    @property
    def password(self) -> str | None:
        return self.components.password

    @property
    def hostname(self) -> str | None:
        return self.components.hostname

    @property
    def port(self) -> int | None:
        return self.components.port

    @property
    def is_secure(self) -> bool:
        return self.scheme in ('https', 'wss')

    def replace(self, **kwargs: Any) -> Self:
        """
        Replacing parameters in the URL

        Args:
            scheme, netloc, path, query, fragment, username, password, hostname, port
        """
        if (
                'username' in kwargs or
                'password' in kwargs or
                'hostname' in kwargs or
                'port' in kwargs
        ):
            netloc = self._replace_netloc(
                username=kwargs.pop('username', self.username),
                password=kwargs.pop('password', self.password),
                hostname=kwargs.pop('hostname', None),
                port=kwargs.pop('port', self.port)
            )
            kwargs['netloc'] = netloc
        components = self.components._replace(**kwargs)
        return type(self)(components.geturl())

    def _replace_netloc(
            self,
            username: str | None,
            password: str | None,
            hostname: str | None,
            port: int | None
    ) -> str:
        new_netloc = Netloc(
            username=username,
            password=password,
            hostname=hostname,
            port=port
        )
        if new_netloc.hostname is None:
            new_netloc.hostname = self._get_hostname()
        netloc = new_netloc.hostname
        if new_netloc.port is not None:
            netloc += f':{new_netloc.port}'
        if new_netloc.username is not None:
            userpass = new_netloc.username
            if new_netloc.password is not None:
                userpass += f':{new_netloc.password}'
            netloc = f'{userpass}@{netloc}'
        return netloc

    def _get_hostname(self) -> str:
        netloc = self.netloc
        _, _, hostname = netloc.rpartition('@')
        if hostname[-1] != ']':
            hostname = hostname.rsplit(':', 1)[0]
        return hostname

    def _get_url(self, url: str, scope: Scope | None, **components: Any) -> str:
        if scope is not None:
            assert not url, ('Cannot set both "url" and "scope"')
            assert not components, ('Cannot set both "scope" and "kwargs"')
            scheme = scope.get('scheme', 'http')
            server = self._get_server(scope)
            path = scope['path']  # type: ignore[typeddict-item]
            query_string: bytes = scope.get('query_string', b'')  # type: ignore[assignment]
            host_header = self._get_host_header(scope)

            if host_header is not None:
                url = f'{scheme}://{host_header}{path}'
            elif server is None:
                url = path
            else:
                default_port = getattr(DefaultScheme, scheme)  # type: ignore[call-overload]
                if server.port == default_port:
                    url = f'{scheme}://{server.host}{path}'
                else:
                    url = f'{scheme}://{server.host}:{server.port}{path}'

            if query_string:
                url += '?' + query_string.decode()
        elif components:
            assert not url, 'Cannot set both "url" and "**components"'
            url = URL('').replace(**components).components.geturl()
        return url

    def _get_server(self, scope: Scope) -> Server | None:
        if (server := scope.get('server')) is not None:
            return Server(host=server[0], port=server[1])  # type: ignore[index]
        return None

    def _get_host_header(self, scope: Scope) -> str | None:
        for key, value in scope['headers']:  # type: ignore[typeddict-item]
            if key == b'host':
                return value.decode('latin-1')
        return None

    def __eq__(self, other: Any) -> bool:
        return str(self) == str(other)

    def __repr__(self) -> str:
        url = str(self)
        if self.password:
            url = str(self.replace(password='********'))
        return f'{type(self).__name__}({repr(url)})'

    def __str__(self) -> str:
        return self._url
