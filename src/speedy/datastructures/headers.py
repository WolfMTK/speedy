from typing import Mapping, Iterable, TypeVar

from multidict import CIMultiDictProxy, MultiMapping, CIMultiDict

from .multi_dicts import MultiMixin

RawHeaders = TypeVar('RawHeaders')


class Headers(CIMultiDictProxy[str], MultiMixin[str]):
    def __init__(
            self,
            headers: Mapping[str, str] | Iterable[tuple[bytes, bytes]] | MultiMapping | None = None
    ) -> None:
        self._init_headers(headers)
        self._headers_list: RawHeaders | None = None

    @property
    def raw(self) -> RawHeaders | None:
        """ Raw header value. """
        if not self._headers_list:
            self._headers_list = self._encode_headers(
                (key, value) for key in set(self) for value in self.getall(key)
            )
        return self._headers_list

    def _encode_headers(self, headers: Iterable[tuple[str, str]]) -> RawHeaders:
        return [(key.lower().encode('latin-1'), value.encode('latin-1')) for key, value in headers]

    def _init_headers(
            self,
            headers: Mapping[str, str] | Iterable[tuple[bytes, bytes] | MultiMapping | None]
    ) -> None:
        if isinstance(headers, MultiMapping):
            super().__init__(headers)
        else:
            headers_stack = {}
            if headers:
                if isinstance(headers, Mapping):
                    headers_stack = headers
                else:
                    headers_stack = [(key.decode('latin-1'), value.decode('latin-1')) for key, value in headers]
            super().__init__(CIMultiDict(headers_stack))


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
