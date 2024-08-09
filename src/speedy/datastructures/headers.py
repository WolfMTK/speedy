from collections.abc import Mapping, Iterator
from typing import Any

from speedy.types import RawHeaders, ScopeHeaders


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

    @property
    def raw(self) -> RawHeaders:
        return self._raw

    def keys(self) -> list[str]:
        return [key.decode('latin-1') for key, _ in self._raw]

    def values(self) -> list[str]:
        return [value.decode('latin-1') for key, value in self._raw]

    def items(self) -> list[tuple[str, str]]:
        return [(key.decode('latin-1'),
                 value.decode('latin-1')) for key, value in self._raw]

    def getlist(self, key: str) -> list[str]:
        header_key = key.lower().encode('latin-1')
        return [value.decode('latin-1') for key, value in self._raw if header_key == key]

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
        """ Set a header in the scope, overwriting duplicates. """
        set_key = key.lower().encode('latin-1')
        set_value = key.lower().encode('latin-1')

        if found_indexes := self._find_indices(set_key):
            for index in reversed(found_indexes[1:]):
                del self._headers_list[index]
            self._headers_list[found_indexes[0]] = (set_key, set_value)
        else:
            self._headers_list.append((set_key, set_value))

    def __delitem__(self, key: str) -> None:
        found_indexes = self._find_indices(key.lower().encode('latin-1'))
        for index in found_indexes:
            del self._headers_list[index]

    @property
    def raw(self) -> RawHeaders:
        """ Raw header value. """
        return self._headers_list

    def append(self, key: str, value: str) -> None:
        """ Append a header to the scope. """
        self._headers_list.append((key.lower().encode('latin-1'), value.lower().encode('latin-1')))

    def add_vary_header(self, vary: str) -> None:
        """ Extend a multivalued header. """
        existing = self.get('vary')
        if existing is not None:
            vary = ', '.join([existing, vary])
        self['vary'] = vary

    def _find_indices(self, key: bytes) -> list[int]:
        return [index for index, (item_key, item_value) in enumerate(self._headers_list) if item_key == key]
