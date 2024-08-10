from __future__ import annotations

import sys
from collections.abc import Mapping, Iterator
from typing import Any

from speedy.types import RawHeaders, ScopeHeaders

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class Headers(Mapping[str, str]):
    def __init__(
            self,
            headers: Mapping[str, str] | None = None,
            raw: RawHeaders | None = None,
            scope: ScopeHeaders | None = None
    ) -> None:
        self._raw: RawHeaders = self._get_raw(headers, raw, scope)

    def __getitem__(self, item: str) -> str:
        header_key = item.lower().encode('latin-1')
        for key, value in self._raw:
            if header_key == key:
                return value.decode('latin-1')
        raise KeyError(item)

    def __contains__(self, item: Any) -> bool:
        header_key = item.lower().encode('latin-1')
        for key, _ in self._raw:
            if header_key == key:
                return True
        return False

    def __iter__(self) -> Iterator[Any]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self._raw)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Headers):
            return False
        return sorted(self._raw) == sorted(other._raw)

    def __repr__(self) -> str:
        name = type(self).__name__
        as_dict = dict(self.items())
        if len(as_dict) == len(self):
            return f'{name}({as_dict!r})'
        return f'{name}(raw={self.raw!r})'

    @property
    def raw(self) -> RawHeaders:
        """ Get RawHeaders. """
        return self._raw.copy()

    def keys(self) -> list[str]:
        """ Get keys. """
        return [key.decode('latin-1') for key, _ in self._raw]

    def values(self) -> list[str]:
        """ Get values. """
        return [value.decode('latin-1') for key, value in self._raw]

    def items(self) -> list[tuple[str, str]]:
        """ Get items. """
        return [(key.decode('latin-1'),
                 value.decode('latin-1')) for key, value in self._raw]

    def getlist(self, key: str) -> list[str]:
        """ Get list values. """
        header_key = key.lower().encode('latin-1')
        return [value.decode('latin-1') for key, value in self._raw if header_key == key]

    def mutablecopy(self) -> MutableHeaders:
        return MutableHeaders(raw=self.raw)

    def _get_raw(self,
                 headers: Mapping[str, str] | None = None,
                 raw: RawHeaders | None = None,
                 scope: ScopeHeaders | None = None) -> RawHeaders:
        if headers is not None:
            if raw is not None:
                raise AttributeError('Cannot set both "headers" and "raw".')

            if scope is not None:
                raise AttributeError('Cannot set both "headers" and "scope".')

            return [(key.lower().encode('latin-1'),
                     value.encode('latin-1')) for key, value in headers.items()]
        elif raw is not None:
            if scope is not None:
                raise AttributeError('Cannot set both "raw" and "scope".')
            return raw
        elif scope is not None:
            return list(scope['headers'])
        return []


class MutableHeaders(Headers):
    def __setitem__(self, key: str, value: str) -> None:
        key = key.lower().encode('latin-1')
        value = value.encode('latin-1')

        updated_index = None
        removed_indexes = []
        for index, (_key, _) in enumerate(self._raw):
            if key == _key:
                if updated_index is None:
                    updated_index = index
                    continue
                removed_indexes.append(index)

        if updated_index is not None:
            self._raw[updated_index] = (key, value)
        else:
            self._raw.append((key, value))

        for index in removed_indexes:
            del self._raw[index]

    def __delitem__(self, key: str) -> None:
        key = key.lower().encode('latin-1')

        indexes = []
        for index, (_key, _) in enumerate(self._raw):
            if key == _key:
                indexes.append(index)

        for index in indexes:
            del self._raw[index]

    def __ior__(self, other: Mapping[str, str]) -> Self:
        if not isinstance(other, Mapping):
            raise TypeError(f'Expected a mapping but got {type(other).__name__}')
        self.update(other)
        return self

    def __or__(self, other: Mapping[str, str]) -> Self:
        if not isinstance(other, Mapping):
            raise TypeError(f'Expected a mapping but got {type(other).__name__}')
        mutable_headers = self.mutablecopy()
        mutable_headers.update(other)
        return mutable_headers

    @property
    def raw(self) -> RawHeaders:
        """ Get RawHeaders. """
        return self._raw

    def update(self, other: Mapping[str, str]) -> None:
        """ Update RawHeaders. """
        for key, val in other.items():
            self[key] = val

    def append(self, key: str, value: str) -> None:
        """ Append a header, preserving any duplicate entries. """
        self._raw.append((key.lower().encode('latin-1'), value.encode('latin-1')))

    def setdefault(self, key: str, value: str) -> str:
        """ Set default key and value in RawHeaders. """
        key_header = key.lower().encode('latin-1')
        value_header = value.encode('latin-1')

        for index, (_key, _value) in enumerate(self._raw):
            if key_header == _key:
                return _value.decode('latin')
        self._raw.append((key_header, value_header))
        return value

    def add_vary_header(self, vary: str) -> None:
        """ Extend a multivalued header. """
        existing = self.get('vary')
        if existing is not None:
            vary = ', '.join([existing, vary])
        self['vary'] = vary
