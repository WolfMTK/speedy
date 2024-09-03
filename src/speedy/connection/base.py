from typing import Generic, NoReturn, Any

from speedy._parsers import parse_cookie_string
from speedy.datastructures import URL, Headers, QueryParams, Address, State
from speedy.exceptions import SessionException, AuthException
from speedy.protocols.app import ASGIApplication
from speedy.protocols.connection import UserT, AuthT, StateT
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable, Message


async def empty_receive() -> NoReturn:
    """ Serves as a placeholder send function. """
    raise RuntimeError()


async def empty_send(_: Message) -> NoReturn:
    """ Serves as a placeholder send function. """
    raise RuntimeError()


class ASGIConnection(Generic[UserT, AuthT, StateT]):
    """ The base ASGI connection class. """

    def __init__(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable = empty_receive,
            send: ASGISendCallable = empty_send,
    ) -> None:
        self.scope = scope
        self.receive = receive
        self.send = send
        self._url: URL | None = None
        self._base_url: URL | None = None
        self._query_params: QueryParams | None = None
        self._cookies: None | dict[str, str] = None
        self._state: StateT | None = None
        self._headers: Headers | None = None

    @property
    def app(self) -> ASGIApplication:
        """ Return the ASGI application. """
        return self.scope['app']

    @property
    def url(self) -> URL:
        """ Return the URL. """
        if self._url is None:
            self._url = URL.from_scope(self.scope)
        return self._url

    @property
    def base_url(self) -> URL:
        """ Return the base URL. """
        if self._base_url is None:
            scope = dict(self.scope)
            root_path = scope.get('root_path', '')
            app_root_path = scope.get('app_root_path', root_path)
            path = app_root_path
            if not path.endswith('/'):
                path += '/'
            scope['path'] = path
            scope['query_string'] = b''
            scope['root_path'] = app_root_path
            self._base_url = URL.from_scope(scope)
        return self._base_url

    @property
    def headers(self) -> Headers:
        """ Return the headers. """
        if self._headers is None:
            self._headers = Headers(scope=self.scope)
        return self._headers

    @property
    def query_params(self) -> QueryParams:
        """ Return the query params. """
        if self._query_params is None:
            self._query_params = QueryParams(self.scope['query_string'])
        return self._query_params

    @property
    def path_params(self) -> dict[str, Any,]:
        """ Return the path params. """
        return self.scope['path_params']

    @property
    def cookies(self) -> dict[str, str]:
        """ Return the cookies. """
        if self._cookies is None:
            cookies = {}
            cookie_header = self.headers.get('cookie')
            if cookie_header:
                cookies = parse_cookie_string(cookie_header)
            self._cookies = cookies
        return self._cookies

    @property
    def client(self) -> Address | None:
        """ Return the client address. """
        client = self.scope.get('client')
        return Address(*client) if client is not None else None

    @property
    def session(self) -> dict[str, Any]:
        """ Return the session for this connection of a session was previously set in the scope. """
        if 'session' not in self.scope:
            # TODO: add a detailed error description
            raise SessionException('`session` is not defined in scope')
        return self.scope['session']

    @property
    def auth(self) -> AuthT:
        """ Return the auth data if this connection's scope. """
        if 'auth' not in self.scope:
            # TODO: add a detailed error description
            raise AuthException('`auth` is not defined in scope')
        return self.scope['auth']

    @property
    def user(self) -> UserT:
        """ Return the user data if this connection's scope. '"""
        if 'user' not in self.scope:
            # TODO: add a detailed error description
            raise AuthException('`user` is not defined in scope')
        return self.scope['user']

    @property
    def state(self) -> StateT:
        """ Return the state of this connection. '"""
        if self._state is None:
            self.scope.setdefault('state', {})
            self._state = State(self.scope['state'])
        return self._state

    def url_for(self, name: str, **path_params: Any) -> URL:
        """ Return the url for a given route handler name. """
        app: ASGIApplication = self.scope['app']
        url_path = app.route_reverse(name, **path_params)
        return URL(url_path)
