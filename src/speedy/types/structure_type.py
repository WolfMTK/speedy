from collections.abc import MutableMapping
from typing import Any

type RawHeaders = list[tuple[bytes, bytes]]
type ScopeHeaders = MutableMapping[str, Any]
