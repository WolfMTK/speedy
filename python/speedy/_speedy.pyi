from abc import ABC, abstractmethod
from collections.abc import ItemsView, Iterable, Iterator, KeysView, Mapping, MutableMapping, Sequence, ValuesView
from datetime import datetime
from typing import Any, Literal, NamedTuple, Self

from speedy.background import BackgroundTask
from speedy.types import RawHeaders

# datastructures.rs
class ImmutableState(Mapping[str, Any]):
    """An object meant to store arbitrary state."""

    def __init__(
        self,
        state: ImmutableState | Mapping[str, Any] | Iterable[tuple[str, Any]],
        copy_data: bool = ...,
    ) -> None: ...
    def __getitem__(self, key: str) -> Any:
        """
        Get the value for the corresponding key
        from the wrapped state object using subscription notation.
        """
        ...

    def __getattr__(self, key: str) -> Any:
        """
        Get the value for the corresponding key
        from the wrapped state object using attribute notation.
        """
        ...

    def __iter__(self) -> Iterator[str]:
        """Return an iterator iterating the wrapped state dict."""
        ...

    def __len__(self) -> int:
        """Return length of the wrapped state dict."""
        ...

    def __repr__(self) -> str: ...
    def __copy__(self) -> Self:
        """Return a shallow copy of the given state object."""
        ...

    def as_dict(self) -> dict[str, Any]:
        """Return a shallow copy of the wrapped state dict as a dictionary."""
        ...

    def mutable_copy(self) -> State:
        """Return a mutable copy of the state object."""
        ...

class State(ImmutableState, MutableMapping[str, Any]):
    """An object that can be used to store arbitrary state."""

    def __init__(
        self,
        state: ImmutableState | Mapping[str, Any] | Iterable[tuple[str, Any]] | None = ...,
        copy_data: bool = ...,
    ) -> None: ...
    def __setitem__(self, key: str, value: Any) -> None:
        "Set an item in the state using subscription notation."
        ...

    def __delitem__(self, key: str) -> None:
        """
        Delete the value from the key
        from the wrapped state object using subscription notation.
        """
        ...

    def __setattr__(self, key: str, value: Any) -> None:
        """Set an item in the state using attribute notation."""
        ...

    def __delattr__(self, key: str) -> None:
        """
        Delete the value from the key
        from the wrapped state object using attribute notation.
        """
        ...

    def copy(self) -> Self:
        """Return a shallow copy of the state object."""
        ...

    def immutable_copy(self) -> ImmutableState:
        """Return a shallow copy of the state object, setting it to be frozen."""
        ...

class Address(NamedTuple):
    """Just a network address."""

    host: str
    port: int

class URL:
    """Representation and modification utilities of a URL."""

    def __init__(self, url: str | URL | URLPath | None = ...) -> None: ...
    def __str__(self) -> str: ...
    def __repr__(self) -> str: ...
    def __eq__(self, other: object) -> bool: ...
    @property
    def scheme(self) -> str:
        """scheme in the URL."""
        ...

    @property
    def hostname(self) -> str | None:
        """hostname in the URL."""
        ...

    @property
    def port(self) -> int | None:
        """port in the URL."""
        ...

    @property
    def netloc(self) -> str:
        """netloc in the URL."""
        ...

    @property
    def username(self) -> str | None:
        """username in the URL."""
        ...

    @property
    def password(self) -> str | None:
        """password in the URL."""
        ...

    @property
    def path(self) -> str:
        """path in the URL."""
        ...

    @property
    def query(self) -> str:
        """query in the URL."""
        ...

    @property
    def fragment(self) -> str:
        """fragment in the URL."""
        ...

    @property
    def is_secure(self) -> bool:
        """Check if the URL is secure."""
        ...

    def replace(self, **kwargs: Any) -> Self:
        """Replace components in the URL."""
        ...

    def replace_query_params(self, **kwargs: Any) -> Self:
        """Replace query parameters in the URL."""
        ...

    def include_query_params(self, **kwargs: Any) -> Self:
        """Include query parameters in the URL."""
        ...

    def remove_query_params(self, keys: str | Sequence[str]) -> URL:
        """Remove query parameters in the URL."""
        ...

class URLPath:
    """Create an absolute URL."""

    path: str | URL
    base: str | URL

    def __init__(self, path: str | URL, base: str | URL) -> None: ...
    def __str__(self) -> str: ...
    def __repr__(self) -> str: ...

class Headers(Mapping[str, str]):
    def __init__(
        self,
        headers: Mapping[str, str] | None = ...,
        raw: RawHeaders | None = ...,
        scope: Mapping[str, Any] | None = ...,
    ) -> None: ...
    def __getitem__(self, item: str) -> str: ...
    def __contains__(self, item: object) -> bool: ...
    def __iter__(self) -> Iterator[str]: ...
    def __len__(self) -> int: ...
    def __eq__(self, other: object) -> bool: ...
    def __repr__(self) -> str: ...
    @property
    def raw(self) -> RawHeaders:
        """Get RawHeaders."""
        ...

    @classmethod
    def from_scope(cls, scope: Mapping[str, Any]) -> Self:
        """Create headers from a send-message."""
        ...

    def keys(self) -> KeysView[str]:
        """Get keys."""
        ...

    def values(self) -> ValuesView[str]:
        """Get values."""
        ...

    def items(self) -> ItemsView[str, str]:
        """Get items."""
        ...

    def getlist(self, key: str) -> list[str]:
        """Get list values."""
        ...

    def mutablecopy(self) -> MutableHeaders:
        """Get a shallow copy of the header object."""
        ...

class MutableHeaders(Headers):
    def __setitem__(self, key: str, value: str) -> None: ...
    def __delitem__(self, key: str) -> None: ...
    def __ior__(self, other: Mapping[str, str]) -> Self: ...
    def __or__(self, other: Mapping[str, str]) -> MutableHeaders: ...
    @property
    def raw(self) -> RawHeaders:
        """Get RawHeaders."""
        ...

    def update(self, other: Mapping[str, str]) -> None:
        """Update RawHeaders."""
        ...

    def append(self, key: str, value: str) -> None:
        """Append a header, preserving any duplicate entries."""
        ...

    def setdefault(self, key: str, value: str) -> str:
        """Set default key and value in RawHeaders."""
        ...

    def add_vary_header(self, vary: str) -> None:
        """Extend a multivalued header."""
        ...

class _MultiMapping[Key, Value](ABC):
    def __setitem__(self, key: Key, values: list[Value]) -> None: ...
    def __getitem__(self, key: Key) -> Value: ...
    def __delitem__(self, key: Any) -> None: ...
    def __contains__(self, key: Any) -> bool: ...
    def __len__(self) -> int: ...
    def __eq__(self, other: Any) -> bool: ...
    def __repr__(self) -> str: ...
    def __iter__(self) -> Iterator[Key]: ...
    @abstractmethod
    def update(
        self, *args: Mapping[Key, Value] | _MultiMapping[Key, Value] | list[tuple[Any, Any]], **kwargs: Any
    ) -> None: ...
    @abstractmethod
    def get(self, key: Any, default: Any): ...
    @abstractmethod
    def append(self, key: Any, value: Any) -> None: ...
    @abstractmethod
    def getList(self, key: Any) -> list[Value]: ...
    @abstractmethod
    def clear(self) -> None: ...
    @abstractmethod
    def pop(self, key: Any, default: Any): ...
    @abstractmethod
    def popitem(self) -> tuple[Any, Any]: ...
    @abstractmethod
    def poplist(self, key: Any) -> list[Any]: ...
    @abstractmethod
    def keys(self) -> KeysView[Key]: ...
    @abstractmethod
    def values(self) -> ValuesView[Value]: ...
    @abstractmethod
    def items(self) -> ItemsView[Key, Value]: ...
    @abstractmethod
    def multi_items(self) -> list[tuple[Key, Value]]: ...

class ImmutableMultiDict[Key, Value](_MultiMapping[Key, Value]):
    """Immutable MultiDict."""

    def __init__(
        self, *args: _MultiMapping[Key, Value] | Mapping[Key, Value] | Iterable[tuple[Key, Value]], **kwargs: Any
    ) -> None: ...
    def get(self, key: Any, default: Any = None) -> Any:
        """Get value."""
        ...

    def update(
        self, *args: Mapping[Key, Value] | _MultiMapping[Key, Value] | list[tuple[Any, Any]], **kwargs: Any
    ) -> None:
        """Update items"""
        ...

    def keys(self) -> KeysView[Key]:
        """Get keys."""
        ...

    def values(self) -> ValuesView[Value]:
        """Get values."""
        ...

    def items(self) -> ItemsView[Key, Value]:
        """Get items."""
        ...

    def clear(self) -> None:
        """Clear items."""
        ...

    def pop(self, key: Any, default: Any = None):
        """Pop element in collection."""
        ...

    def popitem(self) -> tuple[Any, Any]:
        """Popitem element in collection."""
        ...

    def poplist(self, key: Any) -> list[Any]:
        """Poplist element in collection."""
        ...

    def append(self, key: Any, value: Any) -> None:
        """Append element in collection."""
        ...

    def getList(self, key: Any) -> list[Value]:
        """Get array elements."""
        ...

    def multi_items(self) -> list[tuple[Key, Value]]:
        """Get items."""
        ...

class MultiDict(ImmutableMultiDict[Any, Any]):
    """Dictionary with the support for duplicate keys."""

    def setdefault(self, key: Any, default: Any = ...) -> Any:
        """Set default value."""
        ...

    def setlist(self, key: Any, values: list[Any]) -> None:
        """Set list."""
        ...

# responses.rs
class Response:
    """An HTTP response."""

    status_code: int
    media_type: str | None
    charset: str
    background: BackgroundTask | None
    body: bytes | memoryview

    def __new__(
        cls,
        content: Any = ...,
        status_code: int = ...,
        headers: Mapping[str, str] | None = ...,
        media_type: str | None = ...,
        background: BackgroundTask | None = ...,
    ) -> Self: ...
    @property
    def headers(self) -> MutableHeaders:
        """Get a mutable view over the response's headers."""
        ...

    @property
    def raw_headers(self) -> RawHeaders:
        """Get the raw (name, value) header pairs."""
        ...

    @raw_headers.setter
    def raw_headers(self, value: RawHeaders) -> None: ...
    def set_cookie(
        self,
        key: str,
        value: str = ...,
        max_age: int | None = ...,
        expires: datetime | str | int | None = ...,
        path: str | None = ...,
        domain: str | None = ...,
        secure: bool = ...,
        httponly: bool = ...,
        samesite: Literal["lax", "strict", "none"] | None = ...,
        partitioned: bool = ...,
    ) -> None:
        """Set a cookie on the response."""
        ...

    def delete_cookie(
        self,
        key: str,
        path: str = ...,
        domain: str | None = ...,
        secure: bool = ...,
        httponly: bool = ...,
        samesite: Literal["lax", "strict", "none"] | None = ...,
        partitioned: bool = ...,
    ) -> None:
        """Delete a cookie by expiring it immediately."""
        ...
