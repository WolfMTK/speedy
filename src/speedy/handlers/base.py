from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Mapping

from speedy import Router
from speedy.types import (
    AsyncAnyCallable,
    TypeDecodersSequence,
    TypeEncodersMap,
    ExceptionHandlersMap,
    Middleware,
    ParametersMap,
)
from speedy.utils import join_paths
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
        self.type_decoders = tuple(type_decoders or ())
        self.type_encoders = dict(type_encoders or {})

    def merge(self, *others: Router) -> BaseRouteHandler:
        """ Merges another route handler with this route handlers. """
        return type(self)(**self._get_merge_opts(others))

    def _get_paths(self, path: str | Sequence[str] | None) -> set[str]:
        if path and isinstance(path, list):
            return {normalize_path(val) for val in path}
        return {normalize_path(path or "/")}

    def _get_merge_opts(self, others: tuple[Router, ...]) -> dict[str, Any]:
        if others:
            base_path = join_paths([val.path for val in reversed(others)])
        else:
            base_path = ""

        merge_opts: dict[str, Any] = {
            "fn": self.fn,
            "name": self.name,
            "path": [join_paths([base_path, p]) for p in self.paths],
            "exception_handlers": {},
            "middleware": (),
            "opt": {},
            "type_decoders": (),
            "type_encoders": {},
            "parameters": {},
        }

        for other in (self, *others):
            merge_opts["exception_handlers"] = getattr(other, "exception_handlers", {}) | merge_opts[
                "exception_handlers"]
            merge_opts["opt"] = getattr(other, "opt", {}) | merge_opts["opt"]
            merge_opts["type_encoders"] = getattr(other, "type_encoders", {}) | merge_opts["type_encoders"]
            merge_opts["parameters"] = getattr(other, "parameters", {}) | merge_opts["parameters"]

            merge_opts["middleware"] = tuple(getattr(other, "middleware", ())) + merge_opts["middleware"]
            merge_opts["type_decoders"] = merge_opts["type_decoders"] + tuple(getattr(other, "type_decoders", ()))

        return merge_opts
