from abc import abstractmethod
from typing import Protocol, TypeVar, Any

from speedy.datastructures import URL, Headers, State, QueryParams, Address
from speedy.protocols.app import ASGIApplication
from speedy.types import Scope, ASGIReceiveCallable, ASGISendCallable

AuthT = TypeVar("AuthT")
UserT = TypeVar("UserT")
StateT = TypeVar("StateT", bound=State)
HandlerT = TypeVar("HandlerT")


class Connection(Protocol[HandlerT, UserT, AuthT, StateT]):
    @property
    @abstractmethod
    def scope(self) -> Scope: ...

    @property
    @abstractmethod
    def receive(self) -> ASGIReceiveCallable: ...

    @property
    @abstractmethod
    def send(self) -> ASGISendCallable: ...

    @property
    @abstractmethod
    def app(self) -> ASGIApplication: ...

    @property
    @abstractmethod
    def route_handler(self) -> HandlerT: ...

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
    def path_params(self) -> dict[str, Any,]: ...

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

    @abstractmethod
    def set_session(self, value: dict[str, Any] | None) -> None: ...

    @abstractmethod
    def clear_session(self) -> None: ...
