from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import KeysView, ValuesView, ItemsView, Mapping, Iterator, Iterable
from typing import Any


class MultiMapping[_Key, _Value](ABC):
    _dict: dict[_Key, _Value]
    _stack: list[tuple[Any, Any]]

    def __init__(
            self,
            *args: MultiMapping[_Key, _Value] | Mapping[_Key, _Value] | Iterable[tuple[_Key, _Value]],
            **kwargs: Any
    ) -> None:
        self._check_args(*args)

    def __setitem__(self, key: _Key, values: list[_Value]) -> None:
        items = [(k, v) for (k, v) in self._stack if k != key]
        self._stack = items + [(key, value) for value in values]
        self._dict[key] = values[-1]

    def __getitem__(self, key: _Key) -> _Value:
        return self._dict[key]

    def __delitem__(self, key: Any) -> None:
        self._stack = [(k, v) for k, v in self._stack if k != key]
        del self._dict[key]

    def __contains__(self, key: Any) -> bool:
        return key in self._dict

    def __len__(self) -> int:
        return len(self._dict)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return sorted(self._stack) == sorted(other._stack)

    def __repr__(self) -> str:
        items = self.multi_items()
        return f'{type(self).__name__}({items!r})'

    def __iter__(self) -> Iterator[_Key]:
        return iter(self._dict)

    @abstractmethod
    def update(
            self,
            *args: Mapping[_Key, _Value] | MultiMapping[_Key, _Value] | list[tuple[Any, Any]],
            **kwargs: Any
    ) -> None:
        ...

    @abstractmethod
    def get(self, key: Any, default: Any):
        ...

    @abstractmethod
    def append(self, key: Any, value: Any) -> None:
        ...

    @abstractmethod
    def getList(self, key: Any) -> list[_Value]:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...

    @abstractmethod
    def pop(self, key: Any, default: Any):
        ...

    @abstractmethod
    def popitem(self) -> tuple[Any, Any]:
        ...

    @abstractmethod
    def poplist(self, key: Any) -> list[Any]:
        ...

    @abstractmethod
    def keys(self) -> KeysView[_Key]:
        ...

    @abstractmethod
    def values(self) -> ValuesView[_Value]:
        ...

    @abstractmethod
    def items(self) -> ItemsView[_Key, _Value]:
        ...

    @abstractmethod
    def multi_items(self) -> list[tuple[_Key, _Value]]:
        ...

    def _check_args(
            self,
            *args: MultiMapping[_Key, _Value] | Mapping[_Key, _Value] | Iterable[tuple[_Key, _Value]]
    ) -> None:
        if not len(args) < 2:
            raise AttributeError('Too many arguments.')
