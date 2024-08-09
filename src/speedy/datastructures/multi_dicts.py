from __future__ import annotations

from collections.abc import KeysView, ValuesView, ItemsView
from typing import Mapping, Iterable, Any

from speedy.protocols import MultiMapping


class ImmutableMultiDict[_Key, _Value](MultiMapping[_Key, _Value]):
    """ Immutable MultiDict. """

    def __init__(
            self,
            *args: MultiMapping[_Key, _Value] | Mapping[_Key, _Value] | Iterable[tuple[_Key, _Value]],
            **kwargs: Any
    ) -> None:
        self._check_args(*args)
        items = self._get_items(*args, **kwargs)
        self._stack = items
        self._dict = {key: value for key, value in items}

    def get(self, key: Any, default: Any = None) -> Any:
        """ Get value. """
        return self._dict.get(key, default)

    def update(
            self,
            *args: Mapping[_Key, _Value] | MultiMapping[_Key, _Value] | list[tuple[Any, Any]],
            **kwargs: Any
    ) -> None:
        """ Update items """
        value = ImmutableMultiDict(*args, **kwargs)
        items = [(k, v) for k, v in self._stack if k not in value.keys()]
        self._stack = items + value.multi_items()
        self._dict.update(value)

    def keys(self) -> KeysView[_Key]:
        """ Get keys. """
        return self._dict.keys()

    def values(self) -> ValuesView[_Value]:
        """ Get values. """
        return self._dict.values()

    def items(self) -> ItemsView[_Key, _Value]:
        """ Get items. """
        return self._dict.items()

    def clear(self) -> None:
        """ Clear items. """
        self._dict.clear()
        self._stack.clear()

    def pop(self, key: Any, default: Any = None):
        """ Pop element in collection. """
        self._stack = [(k, v) for k, v in self._stack if k != key]
        return self._dict.pop(key, default)

    def popitem(self) -> tuple[Any, Any]:
        """ Popitem element in collection. """
        key, value = self._dict.popitem()
        self._stack = [(k, v) for k, v in self._stack if k != key]
        return key, value

    def poplist(self, key: Any) -> list[Any]:
        """ Poplist element in collection. """
        values = [v for k, v in self._stack if k == key]
        self.pop(key)
        return values

    def append(self, key: Any, value: Any) -> None:
        """ Append element in collection. """
        self._stack.append((key, value))
        self._dict[key] = value

    def getList(self, key: Any) -> list[_Value]:
        """ Get array elements. """
        return [v for k, v in self._stack if k == key]

    def multi_items(self) -> list[tuple[_Key, _Value]]:
        """ Get items. """
        return list(self._stack)

    def _get_items(
            self,
            *args: MultiMapping[_Key, _Value] | Mapping[_Key, _Value] | Iterable[tuple[_Key, _Value]],
            **kwargs: Any
    ) -> list[tuple[Any, Any]]:
        value = args[0] if args else []
        if kwargs:
            value = ImmutableMultiDict(value).multi_items() + ImmutableMultiDict(kwargs).multi_items()
        if not value:
            return []
        elif hasattr(value, 'multi_items'):
            return list(value.multi_items())
        elif hasattr(value, 'items'):
            return list(value.items())
        return list(value)

    def _check_args(
            self,
            *args: MultiMapping[_Key, _Value] | Mapping[_Key, _Value] | Iterable[tuple[_Key, _Value]]
    ) -> None:
        if not len(args) < 2:
            raise AttributeError('Too many arguments.')


class MultiDict(ImmutableMultiDict[Any, Any]):
    """ Dictionary with the support for duplicate keys. """

    def __setitem__(self, key: Any, value: Any) -> None:
        self.setlist(key, [value])

    def setdefault(self, key: Any, default: Any = None) -> Any:
        """ Set default value. """
        if key not in self:
            self[key] = default
        return self[key]

    def setlist(self, key: Any, values: list[Any]) -> None:
        """ Set list. """
        if not values:
            self.pop(key, None)
            return None
        super().__setitem__(key, values)
