from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

from speedy.types import EmptyType

if TYPE_CHECKING:
    from speedy.datastructures import Accept, URL, UploadFile, Headers
    from speedy.types.asgi_types import Scope

CONNECTION_STATE = "_ls_connection_state"


@dataclass
class ScopeState:
    """ An object for storing connection state."""

    def __init__(self) -> None:
        ...

    accept: Accept | EmptyType
    base_url: URL | EmptyType
    body: bytes | EmptyType
    content_type: tuple[str, dict[str, str]] | EmptyType
    cookies: dict[str, str] | EmptyType
    form: dict[str, str | list[str] | UploadFile] | EmptyType
    headers: Headers | EmptyType
    is_cached: bool | EmptyType
    msgpack: Any | EmptyType
    parsed_query: tuple[tuple[str, str], ...] | EmptyType
    response_compressed: bool | EmptyType
    response_started: bool
    session_id: str | None | EmptyType
    url: URL | EmptyType

    @classmethod
    def from_scope(cls, scope: Scope) -> Self:
        """ Create a new `ConnectionState` object from a scope. """
        base_scope = scope.setdefault("state", {})
        if (state := base_scope.get(CONNECTION_STATE)) is None:
            state = base_scope[CONNECTION_STATE] = cls()
        return state
