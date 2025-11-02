from collections.abc import Sequence
from typing import Any

from speedy.types.callable_types import AsyncAnyCallable
from speedy.types.composite_types import TypeDecodersSequence, TypeEncodersMap
from speedy.utils.path import normalize_path


class BaseRouteHandler:
    def __init__(
            self,
            path: str | Sequence[str] | None = None,
            *,
            fn: AsyncAnyCallable,
            name: str | None = None,
            type_decoders: TypeDecodersSequence | None = None,
            type_encoders: TypeEncodersMap | None = None,
            **kwargs: Any,
    ) -> None:
        self.name = name
        self.paths = self._get_paths(path)
        self.fn = fn
        self.type_decoders = type_decoders or {}
        self.type_encoders = type_encoders or {}

    def _get_paths(self, path: str | Sequence[str] | None) -> set[str]:
        if path and isinstance(path, list):
            return {normalize_path(val) for val in path}
        return {normalize_path(path or "/")}
