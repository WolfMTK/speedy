from collections.abc import Mapping, Iterator
from typing import Any


class HTTPConnection(Mapping[str, Any]):
    def __getitem__(self, item: str) -> Any:
        return self.scope[item]  # type: ignore[attr-defined]

    def __iter__(self) -> Iterator[str]:
        return iter(self.scope)  # type: ignore[attr-defined]

    def __len__(self) -> int:
        return len(self.scope)  # type: ignore[attr-defined]
