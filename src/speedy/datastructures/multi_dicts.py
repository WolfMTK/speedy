from abc import ABC
from typing import TypeVar, Generic, Mapping, Iterable, Iterator

from multidict import MultiDict as _MultiDict
from multidict import MultiMapping

T = TypeVar('T')


class MultiMixin(Generic[T], MultiMapping[T], ABC):
    """ Mixin providing common methods for multi dicts. """

    def multi_items(self) -> Iterator[tuple[str, T]]:
        """ Get all keys and values, including duplicates. """
        stack = []

        for key in tuple(self):
            if key in stack:
                continue
            stack.append(key)

            for value in self.getall(key):
                yield key, value


class MultiDict(_MultiDict[T], MultiMixin[T], Generic[T]):
    """ Dictionary with the support for duplicate keys. """

    def __init__(self, args: MultiMapping | Mapping[str, T] | Iterable[tuple[str, T]] | None = None) -> None:
        super().__init__(args or {})
