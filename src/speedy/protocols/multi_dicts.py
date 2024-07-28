from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import KeysView, ValuesView, ItemsView, Mapping
from typing import Any


class MultiMapping[_Key, _Value](ABC):
    @abstractmethod
    def update(
            self,
            *args: Mapping[_Key, _Value] | MultiMapping[_Key, _Value] | list[tuple[Any, Any]],
            **kwargs: Any
    ) -> None: ...

    @abstractmethod
    def get(self, key: Any, default: Any): ...

    @abstractmethod
    def append(self, key: Any, value: Any) -> None: ...

    @abstractmethod
    def getList(self, key: Any) -> list[_Value]: ...

    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def pop(self, key: Any, default: Any): ...

    @abstractmethod
    def popitem(self) -> tuple[Any, Any]: ...

    @abstractmethod
    def poplist(self, key: Any) -> list[Any]: ...

    @abstractmethod
    def keys(self) -> KeysView[_Key]: ...

    @abstractmethod
    def values(self) -> ValuesView[_Value]: ...

    @abstractmethod
    def items(self) -> ItemsView[_Key, _Value]: ...

    @abstractmethod
    def multi_items(self) -> list[tuple[_Key, _Value]]: ...
