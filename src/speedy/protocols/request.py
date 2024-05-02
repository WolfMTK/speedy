from collections.abc import Mapping
from typing import Any


class HTTPConnection(Mapping[str, Any]):
    def __getitem__(self, item):
        return self.scope[item]

    def __iter__(self):
        return iter(self.scope)

    def __len__(self):
        return len(self.scope)
