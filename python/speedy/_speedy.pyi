from collections.abc import Iterable, Iterator, Mapping, MutableMapping
from typing import Any, Self


# datastructures.rs
class ImmutableState(Mapping[str, Any]):
    """An object meant to store arbitrary state."""

    def __init__(
            self,
            state: "ImmutableState | Mapping[str, Any] | Iterable[tuple[str, Any]]",
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

    def mutable_copy(self) -> "State":
        """Return a mutable copy of the state object."""
        ...


class State(ImmutableState, MutableMapping[str, Any]):
    """An object that can be used to store arbitrary state."""

    def __init__(
            self,
            state: "ImmutableState | Mapping[str, Any] | Iterable[tuple[str, Any]] | None" = ...,
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
