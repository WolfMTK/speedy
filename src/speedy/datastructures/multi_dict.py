from abc import ABC
from typing import TypeVar, Generic, Any, Mapping, Iterable, Generator, Self

from multidict import MultiDict as BaseMultiDict
from multidict import MultiMapping, MultiDictProxy

T = TypeVar('T')


class MultiMixin(Generic[T], MultiMapping[T], ABC):
    def dict(self) -> dict[str, list[Any]]:
        """ Return the multi-dict as a dict of lists. """
        return {key: self.getall(key) for key in set(self.keys())}

    def multi_items(self) -> Generator[tuple[str, T], None, None]:
        """ Get all keys and values, including duplicates. """
        for key in set(self):
            for value in self.getall(key):
                yield key, value


class MultiDict(BaseMultiDict[T], MultiMixin[T], Generic[T]):
    def __init__(
            self,
            args: MultiMapping | Mapping[str, T] | Iterable[tuple[str, T]] | None = None  # type: ignore[type-arg]
    ) -> None:
        super().__init__(args or {})

    def immutable(self) -> 'ImmutableMultiDict'[T]:
        return ImmutableMultiDict[T](self)

    def copy(self) -> Self:
        """ Return a shallow copy. """
        return type(self)(list(self.multi_items()))


class ImmutableMultiDict(MultiDictProxy[T], MultiMixin[T], Generic[T]):
    def __init__(
            self,
            args: MultiMapping | Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None  # type: ignore[type-arg]
    ) -> None:
        super().__init__(BaseMultiDict(args) or {})  # type: ignore[arg-type]

    def mutable_copy(self) -> MultiDict[T]:
        """ Create a mutable copy as a `MultiDict`. """
        return MultiDict(list(self.multi_items()))

    def copy(self) -> Self:  # type: ignore[override]
        """ Return a shallow copy. """
        return type(self)(self.items())
