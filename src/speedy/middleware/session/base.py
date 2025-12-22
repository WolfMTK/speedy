from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Any

from speedy import ScopeType
from speedy.connection.base import ASGIConnection
from speedy.types import Scopes, SAMESITE

ConfigT = TypeVar("ConfigT", bound="BaseBackendConfig")
BaseSessionBackendT = TypeVar("BaseSessionBackendT", bound="BaseSessionBackend")


class BaseBackendConfig(ABC, Generic[BaseSessionBackendT]):
    """ Configuration for session middleware backends. """

    _backend_class: type[BaseSessionBackendT]

    key: str
    max_age: int
    scopes: Scopes = {ScopeType.HTTP, ScopeType.WEBSOCKET}
    path: str
    domain: str | None
    secure: bool
    httponly: bool
    samesite: SAMESITE
    exclude: str | list[str] | None
    exclude_opt_key: str


class BaseSessionBackend(ABC, Generic[ConfigT]):
    def __init__(self, config: ConfigT) -> None:
        self.config = config

    @abstractmethod
    async def load_from_connection(self, connection: ASGIConnection) -> dict[str, Any,]:
        """ Load session data from a connection and return it as a dictionary to be used in the application scope. """
