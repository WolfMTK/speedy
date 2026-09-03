from copy import deepcopy
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Self, Iterator, MutableMapping

from speedy.exceptions import StateException


class ImmutableState(Mapping[str, Any]):
    """An object meant to store arbitrary state."""
    __slots__ = ("_data", "_proxy")

    def __init__(
            self,
            state: Self | Mapping[str, Any] | Iterable[tuple[str, Any]],
            copy_data: bool = True,
    ) -> None:
        if isinstance(state, ImmutableState):
            data = state._data
        elif isinstance(state, (Mapping, Iterable)):
            data = dict(state)
        else:
            raise StateException(f"Invalid state type: {type(state)}")

        object.__setattr__(self, "_data", deepcopy(data) if copy_data else data)
        object.__setattr__(self, "_proxy", MappingProxyType(self._data))

    def __getitem__(self, key: str) -> Any:
        """
        Get the value for the corresponding key
        from the wrapped state object using subscription notation.
        """
        return self._proxy[key]

    def __getattr__(self, key: str) -> Any:
        """
        Get the value for the corresponding key
        from the wrapped state object using attribute notation.
        """
        try:
            return self._proxy[key]
        except KeyError:
            raise AttributeError(f"Attribute `{key}` not found")

    def __iter__(self) -> Iterator[str]:
        """Return an iterator iterating the wrapped state dict."""
        return iter(self._proxy)

    def __copy__(self) -> Self:
        """Return a shallow copy of the given state object."""
        return type(self)(self._data.copy(), copy_data=False)

    def __len__(self) -> int:
        """Return length of the wrapped state dict."""
        return len(self._proxy)

    def __bool__(self) -> bool:
        """Return a boolean indicating whether the wrapped dict instance has values."""
        return bool(self._proxy)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self._data)!r})"

    def as_dict(self) -> dict[str, Any]:
        """Return a shallow copy of the wrapped state dict as a dictionary."""
        return dict(self._proxy)

    def mutable_copy(self) -> "State":
        """Return a mutable copy of the state object."""
        return State(deepcopy(self._data), copy_data=False)


class State(ImmutableState, MutableMapping[str, Any]):
    """An object that can be used to store arbitrary state."""
    __slots__ = ()

    def __init__(
            self,
            state: ImmutableState | Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
            copy_data: bool = True,
    ) -> None:
        super().__init__(state if state is not None else {}, copy_data=copy_data)

    def __getitem__(self, key: str) -> Any:
        """Get the value for the corresponding key
        from the wrapped state object using subscription notation."""
        return self._data[key]

    def __getattr__(self, key: str) -> Any:
        """Get the value for the corresponding key
        from the wrapped state object using attribute notation."""
        try:
            return self._data[key]
        except KeyError:
            raise AttributeError(f"Attribute `{key}` not found")

    def __setitem__(self, key: str, value: Any) -> None:
        "Set an item in the state using subscription notation."
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        """
        Delete the value from the key
        from the wrapped state object using subscription notation.
        """
        del self._data[key]

    def __delattr__(self, key: Any) -> None:
        """
        Delete the value from the key
        from the wrapped state object using attribute notation.
        """
        try:
            del self._data[key]
        except KeyError as err:
            raise AttributeError(f"Attribute {key} not found") from err

    def __setattr__(self, key: str, value: Any) -> None:
        """Set an item in the state using attribute notation."""
        if key in ("_data", "_proxy"):
            raise AttributeError(
                f"Cannot set reserved attribute '{key}' "
                "via attribute notation. Use object.__setattr__() "
                "if you intend to modify internal state.",
            )
        self._data[key] = value

    def __iter__(self) -> Iterator[str]:
        """Return an iterator iterating the wrapped state dict."""
        return iter(self._data)

    def __len__(self) -> int:
        """Return length of the wrapped state dict."""
        return len(self._data)

    def immutable_copy(self) -> ImmutableState:
        """Return a shallow copy of the state object, setting it to be frozen."""
        return ImmutableState(deepcopy(self._data), copy_data=False)

    def copy(self) -> Self:
        """Return a shallow copy of the state object."""
        cls = type(self)
        return cls(self._data.copy(), copy_data=False)
