from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

from speedy.types import (
    AsyncAnyCallable,
    TypeDecodersSequence,
    TypeEncodersMap,
    ExceptionHandlersMap,
    Middleware,
    ParametersMap,
)
from speedy.utils.path import normalize_path


class BaseRouteHandler:
    def __init__(
            self,
            path: str | Sequence[str] | None = None,
            *,
            fn: AsyncAnyCallable,
            exception_handlers: ExceptionHandlersMap | None = None,
            middleware: Sequence[Middleware] | None = None,
            name: str | None = None,
            opt: Mapping[str, Any] | None = None,
            signature_namespace: Mapping[str, Any] | None = None,
            signature_types: Sequence[Any] | None = None,
            parameters: ParametersMap | None = None,
            type_decoders: TypeDecodersSequence | None = None,
            type_encoders: TypeEncodersMap | None = None,
            **kwargs: Any,
    ) -> None:
        self.exception_handlers = exception_handlers or {}
        self.name = name
        self.paths = self._get_paths(path)
        self.fn = fn
        self.type_decoders = type_decoders or {}
        self.type_encoders = type_encoders or {}

    def _get_paths(self, path: str | Sequence[str] | None) -> set[str]:
        if path and isinstance(path, list):
            return {normalize_path(val) for val in path}
        return {normalize_path(path or "/")}
