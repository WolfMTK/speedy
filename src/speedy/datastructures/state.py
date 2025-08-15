from collections.abc import Mapping, Iterator, MutableMapping, Iterable
from copy import deepcopy
from threading import RLock
from types import MappingProxyType
from typing import Any

from speedy.utils.scope.state import CONNECTION_STATE


class ImmutableState(Mapping[str, Any]):
    """ An object meant to store arbitrary state. """
    __slots__ = ("_data", "_proxy", "_copy_data")

    _state: dict[str, Any]

    def __init__(
            self,
            state: "ImmutableState | Mapping[str, Any] | Iterable[tuple[str, Any]]",
            copy_data: bool = True,
    ) -> None:
        if isinstance(state, ImmutableState):
            data = state._data
        elif isinstance(state, Mapping):
            data = dict(state)
        elif isinstance(state, Iterable):
            data = dict(state)
        else:
            raise TypeError(f"Invalid state type: {type(state)}")

        self._data = deepcopy(data) if copy_data else data
        self._proxy = MappingProxyType(self._data)
        object.__setattr__(self, "_copy_data", copy_data)

    def __bool__(self) -> bool:
        """ Return a boolean indicating whether the wrapped dict instance has values. """
        return bool(self._proxy)

    def __getitem__(self, key: str) -> Any:
        """ Get the value for the corresponding key from the wrapped state object using subscription notation. """
        return self._proxy[key]

    def __iter__(self) -> Iterator[str]:
        """ Return an iterator iterating the wrapped state dict. """
        return iter(self._proxy)

    def __len__(self) -> int:
        """ Return length of the wrapped state dict. """
        return len(self._proxy)

    def __getattr__(self, key: str) -> Any:
        """ Get the value for the corresponding key from the wrapped state object using attribute notation. """
        if key in self._proxy:
            return self._proxy[key]
        raise AttributeError(key)

    def __copy__(self) -> "ImmutableState":
        """ Return a shallow copy of the given state object. """
        cls = type(self)
        return cls(self._data, copy_data=False)

    def as_dict(self, exclude_internal: bool = False) -> dict[str, Any]:
        """ Return a shallow copy of the wrapped state dict as a dictionary. """
        if exclude_internal:
            return {k: v for k, v in self._proxy.items() if k != CONNECTION_STATE}
        return dict(self._proxy)

    def mutable_copy(self) -> "State":
        """ Return a mutable copy of the state object. """
        return State(self._data, copy_data=False)

    @classmethod
    def validate(cls, value) -> "ImmutableState":
        """ Parse a value and instantiate state inside a SignatureModel. This allows us to use custom subclasses
        of state, as well as allows users to decide whether state is mutable or immutable. """
        copy_data = getattr(value, "_copy_data", False)
        return cls(value, copy_data=copy_data)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({dict(self._data)!r})"


class State(ImmutableState, MutableMapping[str, Any]):
    """ An object that can be used to store arbitrary state. """
    __slots__ = ("_lock", "_data", "_proxy", "_copy_data")

    def __init__(
            self,
            state: ImmutableState | Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
            copy_data: bool = True,
    ) -> None:
        object.__setattr__(self, "_lock", RLock())
        super().__init__(state if state is not None else {}, copy_data=copy_data)

    def __setitem__(self, key: str, value: Any) -> None:
        """ Set an item in the state using subscription notation. """
        with self._lock:
            self._data[key] = value

    def __delitem__(self, key: str) -> None:
        """ Delete the value from the key from the wrapped state object using subscription notation. """
        with self._lock:
            del self._data[key]

    def __delattr__(self, key: str) -> None:
        """ Delete the value from the key from the wrapped state object using attribute notation. """
        if key in self.__slots__:
            object.__delattr__(self, key)
            return
        try:
            with self._lock:
                del self._data[key]
        except KeyError as e:
            raise AttributeError(f"Attribute {key} not found") from e

    def __setattr__(self, key: str, value: Any) -> None:
        """ Set an item in the state using attribute notation. """
        if key in ("_data", "_proxy"):
            object.__setattr__(self, key, value)
            return
        with self._lock:
            self._data[key] = value

    def immutable_copy(self) -> "ImmutableState":
        """ Return a shallow copy of the state object, setting it to be frozen. """
        with self._lock:
            return ImmutableState(self._data, copy_data=False)

    def copy(self) -> "State":
        """ Return a shallow copy of the state object. """
        with self._lock:
            csl = type(self)
            return csl(self._data, copy_data=False)

    def mutable_copy(self) -> "State":
        with self._lock:
            return State(self._data, copy_data=False)
