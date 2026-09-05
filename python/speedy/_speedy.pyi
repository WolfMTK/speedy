from collections.abc import Iterable, Iterator, Mapping, MutableMapping, Sequence
from typing import Any, NamedTuple, Self

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
