from abc import abstractmethod
from typing import Protocol, Any, TypeVar

from speedy.datastructures import URL, Headers, QueryParams, Address
from speedy.protocols.app import ASGIApplication

AuthT = TypeVar('AuthT')
UserT = TypeVar('UserT')
StateT = TypeVar('StateT')


class Connection(Protocol[UserT, AuthT, StateT]):
    @property
    @abstractmethod
    def app(self) -> ASGIApplication: ...

    @property
    @abstractmethod
    def url(self) -> URL: ...

    @property
    @abstractmethod
    def base_url(self) -> URL: ...

    @property
    @abstractmethod
    def headers(self) -> Headers: ...

    @property
    @abstractmethod
    def query_params(self) -> QueryParams: ...

    @property
    @abstractmethod
    def path_params(self) -> dict[str, Any]: ...

    @property
    @abstractmethod
    def cookies(self) -> dict[str, str]: ...

    @property
    @abstractmethod
    def client(self) -> Address | None: ...

    @property
    @abstractmethod
    def session(self) -> dict[str, Any]: ...

    @property
    @abstractmethod
    def auth(self) -> AuthT: ...

    @property
    @abstractmethod
    def user(self) -> UserT: ...

    @property
    @abstractmethod
    def state(self) -> StateT: ...

    @abstractmethod
    def url_for(self, name: str, **path_params: Any) -> URL: ...
