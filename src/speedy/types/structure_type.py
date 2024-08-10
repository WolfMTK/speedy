from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, TypeAlias

RawHeaders: TypeAlias = list[tuple[bytes, bytes]]

ScopeHeaders: TypeAlias = MutableMapping[str, Any]

StateType: TypeAlias = dict[str, Any]
