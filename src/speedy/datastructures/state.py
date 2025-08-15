from collections.abc import Mapping, Iterator, MutableMapping, Iterable, Callable
from copy import deepcopy
from threading import RLock
from typing import Any


class ImmutableState(Mapping[str, Any]):
    """ An object meant to store arbitrary state. """
    __slots__ = (
        "_deep_copy",
        "_state",
    )

    _state: dict[str, Any]

    def __init__(
            self,
            state: 'ImmutableState | Mapping[str, Any] | Iterable[tuple[str, Any]]',
            deep_copy: bool = True,
    ) -> None:
        if isinstance(state, ImmutableState):
            state = state._state

        if not isinstance(state, dict) and isinstance(state, Iterable):
            state = dict(state)

        super().__setattr__('_deep_copy', deep_copy)
        super().__setattr__("_state", deepcopy(state) if deep_copy else state)

    def __bool__(self) -> bool:
        """ Return a boolean indicating whether the wrapped dict instance has values. """
        return bool(self._state)

    def __getitem__(self, key: str) -> Any:
        """ Get the value for the corresponding key from the wrapped state object using subscription notation. """
        return self._state[key]

    def __iter__(self) -> Iterator[str]:
        """ Return an iterator iterating the wrapped state dict. """
        return iter(self._state)

    def __len__(self) -> int:
        """ Return length of the wrapped state dict. """
        return len(self._state)

    def __getattr__(self, key: str) -> Any:
        """ Get the value for the corresponding key from the wrapped state object using attribute notation. """
        try:
            return self._state[key]
        except KeyError as e:
            raise AttributeError(e) from e

    def __copy__(self) -> 'ImmutableState':
        """ Return a shallow copy of the given state object. """
        cls = type(self)
        return cls(self._state, deep_copy=self._deep_copy)

    @classmethod
    def __get_validators__(
            cls,
    ) -> Iterable[Callable[['ImmutableState | dict[str, Any] | Iterable[tuple[str, Any]]'], 'ImmutableState']]:
        yield cls.validate

    def mutable_copy(self) -> 'State':
        return State(self._state, deep_copy=self._deep_copy)

    def dict(self) -> dict[str, Any]:
        return {key: value for key, value in self._state.items() if key != '_ls_connection_state'}

    @classmethod
    def validate(
            cls,
            value: 'ImmutableState | dict[str, Any] | Iterable[tuple[str, Any]]',
    ) -> 'ImmutableState':
        deep_copy = value._deep_copy if isinstance(value, ImmutableState) else False
        return cls(value, deep_copy=deep_copy)


class State(ImmutableState, MutableMapping[str, Any]):
    """ An object that can be used to store arbitrary state. """
    __slots__ = ("_lock",)

    _lock: RLock

    def __init__(
            self,
            state: ImmutableState | Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
            deep_copy: bool = True,
    ) -> None:
        super().__init__(state if state is not None else {}, deep_copy=deep_copy)
        super().__setattr__('_lock', RLock())

    def __delitem__(self, key: str) -> None:
        """ Delete the value from the key from the wrapped state object using subscription notation. """
        with self._lock:
            del self._state[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """ Set an item in the state using subscription notation. """
        with self._lock:
            self._state[key] = value

    def __setattr__(self, key: str, value: Any) -> None:
        """ Set an item in the state using attribute notation. """
        with self._lock:
            self._state[key] = value

    def __delattr__(self, key: str) -> None:
        """ Delete the value from the key from the wrapped state object using attribute notation. """
        try:
            with self._lock:
                del self._state[key]
        except KeyError as e:
            raise AttributeError from e

    def copy(self) -> 'State':
        """ Return a shallow copy of the state object. """
        cls = type(self)
        return cls(self.dict(), deep_copy=self._deep_copy)

    def immutable_copy(self) -> 'ImmutableState':
        return ImmutableState(self, deep_copy=self._deep_copy)
