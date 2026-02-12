from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from speedy.types import Method, PathParameterDefinition, ASGIAppType, RouteHandlerType


@dataclass
class RouteEntry:
    """ Raw route registration data before compilation. """
    method: Method | str
    path: str
    path_components: list[str | PathParameterDefinition]
    asgi_app: ASGIAppType
    handler: RouteHandlerType
    is_dynamic: bool


@dataclass
class CompileRoute:
    """ A route compiled into a regex pattern for matching. """
    pattern: re.Pattern[str]
    method: Method | str
    asgi_app: ASGIAppType
    handler: RouteHandlerType
    path_template: str
    param_names: list[str] = field(default_factory=list)
    specificity: int = 0


class BaseRouter(ABC):
    """ Interface that every concrete router must implement. """

    @abstractmethod
    def add_route(
            self,
            path: str,
            method: Method | str,
            path_components: list[str | PathParameterDefinition],
            asgi_app: ASGIAppType,
            handler: RouteHandlerType,
            is_dynamic: bool = False,
    ) -> None: ...

    @abstractmethod
    def match(
            self,
            path: str,
            method: Method | None = None,
    ) -> tuple[ASGIAppType, RouteHandlerType, dict[str, str], str] | None: ...

    @abstractmethod
    def clear(self) -> None: ...


class _TrieNode:
    __slots__ = ("children", "param_child", "param_definition", "handlers")

    def __init__(self) -> None:
        self.children: dict[str, _TrieNode] = {}
        self.param_child: _TrieNode | None = None
        self.param_definition: PathParameterDefinition | None = None
        self.handlers: dict[str, tuple[ASGIAppType, RouteHandlerType, str]] = {}


class TrieRouter(BaseRouter):
    """ Trie router. """

    def __init__(self) -> None:
        self.root = _TrieNode()
        self._static_map = {}
        self._route_count = 0

    def __len__(self) -> int:
        return self._route_count

    def add_route(
            self,
            path: str,
            method: Method | str,
            path_components: list[str | PathParameterDefinition],
            asgi_app: ASGIAppType,
            handler: RouteHandlerType,
            is_dynamic: bool = False,
    ) -> None:
        """ Register a route in the trie. """
        self._route_count += 1
        path_template = path

        if not is_dynamic:
            self._static_map[(method, path)] = (asgi_app, handler, path_template)

        node = self.root
        for component in path_components:
            if isinstance(component, PathParameterDefinition):
                if node.param_child is None:
                    node.param_child = _TrieNode()
                    node.param_definition = component
                node = node.param_child
                continue
            child = node.children.get(component)
            if child is None:
                child = _TrieNode()
                node.children[component] = child
            node = child

        node.handlers[method] = (asgi_app, handler, path_template)

    def match(
            self,
            path: str,
            method: Method | None = None,
    ) -> tuple[ASGIAppType, RouteHandlerType, dict[str, str], str] | None:
        """ Find the handler registered for path and method. """
        if method is not None:
            hit = self._static_map.get((method, path)) or self._static_map.get(("asgi", path))
            if hit is not None:
                return hit[0], hit[1], {}, hit[2]
        else:
            for val in ("websocket", "asgi"):
                hit = self._static_map.get((val, path))
                if hit is not None:
                    return hit[0], hit[1], {}, hit[2]

        if path == "/":
            return self._resolve_handler(self.root, method)

        parts = [p for p in path.split("/") if p]
        return self._walk(self.root, parts, 0, method)

    def clear(self) -> None:
        """ Remove all routes and reset the trie to its initial state. """
        self.root = _TrieNode()
        self._static_map.clear()
        self._route_count = 0

    def _walk(
            self,
            node: _TrieNode,
            parts: list[str],
            index: int,
            method: Method | None,
    ) -> tuple[ASGIAppType, RouteHandlerType, dict[str, str], str] | None:

        if index == len(parts):
            return self._resolve_handler(node, method)

        segment = parts[index]

        child = node.children.get(segment)
        if child is not None:
            result = self._walk(child, parts, index + 1, method)
            if result is not None:
                return result

        if node.param_child is not None:
            result = self._walk(node.param_child, parts, index + 1, method)
            if result is not None:
                asgi_app, handler, params, tmpl = result
                params[node.param_definition.name] = segment
                return asgi_app, handler, params, tmpl

        return None

    def _resolve_handler(
            self,
            node: _TrieNode,
            method: Method | None,
    ) -> tuple[ASGIAppType, RouteHandlerType, dict[str, str], str] | None:
        if method is not None:
            entry = node.handlers.get(method) or node.handlers.get("asgi")
        else:
            entry = node.handlers.get("websocket") or node.handlers.get("asgi")
        if entry is not None:
            return entry[0], entry[1], {}, entry[2]
        return None


class RegExpRouter(BaseRouter):
    """ Compiles all routes into per-method combined regular expressions. """

    def __init__(self) -> None:
        self._pending = []
        self._compiled = {}
        self._compiled_meta = {}
        self._built = False
        self._route_count = 0

    def __len__(self) -> int:
        return self._route_count

    def add_route(
            self,
            path: str,
            method: Method | str,
            path_components: list[str | PathParameterDefinition],
            asgi_app: ASGIAppType,
            handler: RouteHandlerType,
            is_dynamic: bool = False,
    ) -> None:
        """ Buffer a route for later compilation. """
        if self._built:
            raise RuntimeError("Cannot add routes after the RegExpRouter matcher has been built.")
        self._pending.append((path, method, path_components, asgi_app, handler, is_dynamic))
        self._route_count += 1

    def build(self) -> RegExpRouter:
        """ Explicitly compile all buffered routes into combined regexes. """
        self._build()
        return self

    def match(
            self,
            path: str,
            method: Method | None = None,
    ) -> tuple[ASGIAppType, RouteHandlerType, dict[str, str], str] | None:
        """ Match path against the compiled combined regex for method. """
        if not self._built:
            self._build()

        methods_to_check: list[str]
        if method is not None:
            methods_to_check = [method, "asgi"]
        else:
            methods_to_check = ["websocket", "asgi"]

        for m in methods_to_check:
            pattern = self._compiled.get(m)
            if pattern is None:
                continue
            match_obj = pattern.match(path)
            if match_obj is None:
                continue

            groups = match_obj.groupdict()
            meta_list = self._compiled_meta[m]

            for i, (param_names, asgi_app, handler, path_template) in enumerate(meta_list):
                route_group = f"_r{i}"
                if groups.get(route_group) is not None:
                    path_params: dict[str, str] = {}
                    for name in param_names:
                        qualified = f"p{i}_{name}"
                        val = groups.get(qualified)
                        if val is not None:
                            path_params[name] = val
                    return asgi_app, handler, path_params, path_template

        return None

    def clear(self) -> None:
        """ Discard all compiled patterns and buffered routes. """
        self._pending.clear()
        self._compiled.clear()
        self._compiled_meta.clear()
        self._built = False
        self._route_count = 0

    def _build(self) -> None:
        if self._built:
            return

        by_method: dict[str, list[tuple[str, list[str | PathParameterDefinition],
        ASGIAppType, RouteHandlerType, bool]]] = {}
        for path, method, components, app, handler, is_dynamic in self._pending:
            by_method.setdefault(method, []).append((path, components, app, handler, is_dynamic))

        for method, entries in by_method.items():
            alternatives: list[str] = []
            meta: list[tuple[list[str], ASGIAppType, RouteHandlerType, str]] = []

            for idx, (path, components, asgi_app, handler, is_dynamic) in enumerate(entries):
                regex_parts: list[str] = []
                param_names: list[str] = []
                for comp in components:
                    if isinstance(comp, PathParameterDefinition):
                        group_name = f"p{idx}_{comp.name}"
                        regex_parts.append(f"(?P<{group_name}>[^/]+)")
                        param_names.append(comp.name)
                    else:
                        escaped = re.escape(comp).replace("\\/", "/")
                        regex_parts.append(escaped)

                pattern_str = "/" + "/".join(regex_parts) if regex_parts else "/"
                alternatives.append(pattern_str)
                path_template = path
                meta.append((param_names, asgi_app, handler, path_template))

            individual_patterns: list[str] = []
            for i, alt in enumerate(alternatives):
                individual_patterns.append(f"(?P<_r{i}>{alt})")

            combined = "^(?:" + "|".join(individual_patterns) + ")$"
            try:
                self._compiled[method] = re.compile(combined)
            except re.error:
                raise ValueError(
                    f"RegExpRouter cannot compile combined pattern for method {method}",
                )
            self._compiled_meta[method] = meta

        self._pending.clear()
        self._built = True


@dataclass(frozen=True)
class RouteAnalysis:
    """ Static analysis of a set of registered routes. """
    total: int = 0
    static_count: int = 0
    dynamic_count: int = 0
    max_depth: int = 0
    max_params_per_route: int = 0
    unique_methods: int = 0
    has_overlapping_params: bool = False

    @property
    def static_ratio(self) -> float:
        """ Fraction of routes that are purely static (0.0 – 1.0). """
        return self.static_count / self.total if self.total else 0.0

    @property
    def dynamic_ratio(self) -> float:
        """ Fraction of routes that contain path parameters (0.0 – 1.0). """
        return self.dynamic_count / self.total if self.total else 0.0


def _analyse_routes(
        pending: list[tuple[str, Method | str, list[str | PathParameterDefinition],
        ASGIAppType, RouteHandlerType, bool]],
) -> RouteAnalysis:
    if not pending:
        return RouteAnalysis()

    static_count = 0
    dynamic_count = 0
    max_depth = 0
    max_params = 0
    methods: set[str] = set()
    param_positions: dict[int, set[str]] = {}

    for path, method, components, _app, _handler, is_dynamic in pending:
        methods.add(method if isinstance(method, str) else str(method))
        depth = len(components)
        if depth > max_depth:
            max_depth = depth

        if is_dynamic:
            dynamic_count += 1
            route_params = 0
            for i, comp in enumerate(components):
                if isinstance(comp, PathParameterDefinition):
                    route_params += 1
                    param_positions.setdefault(i, set()).add(comp.name)
            if route_params > max_params:
                max_params = route_params
        else:
            static_count += 1

    has_overlapping = any(len(names) > 1 for names in param_positions.values())

    return RouteAnalysis(
        total=len(pending),
        static_count=static_count,
        dynamic_count=dynamic_count,
        max_depth=max_depth,
        max_params_per_route=max_params,
        unique_methods=len(methods),
        has_overlapping_params=has_overlapping,
    )


class SmartRouter(BaseRouter):
    """ Analyses route structure and selects the optimal routing algorithm. """

    def __init__(self, routers: list[BaseRouter] | None = None) -> None:
        self.routers = routers or [RegExpRouter(), TrieRouter()]
        self._active_router  = None
        self._analysis = None
        self._pending = []
        self._route_count = 0

    def add_route(
            self,
            path: str,
            method: Method | str,
            path_components: list[str | PathParameterDefinition],
            asgi_app: ASGIAppType,
            handler: RouteHandlerType,
            is_dynamic: bool = False,
    ) -> None:
        """ Buffer a route registration for later analysis and delegation. """
        self._pending.append((path, method, path_components, asgi_app, handler, is_dynamic))
        self._route_count += 1

    @property
    def analysis(self) -> RouteAnalysis | None:
        """ The most recent route analysis. """
        return self._analysis

    def construct(self) -> None:
        """ Analyze all buffered routes, rank candidate routers, and build. """
        for r in self.routers:
            r.clear()
        self._active_router = None

        self._analysis = _analyse_routes(self._pending)
        ranked = self._rank_routers(self._analysis)

        for router in ranked:
            try:
                router.clear()
                for args in self._pending:
                    router.add_route(*args)
                if hasattr(router, 'build'):
                    router.build()
                self._active_router = router
                return
            except (RuntimeError, ValueError, TypeError, re.error):
                continue

        fallback = ranked[-1]
        fallback.clear()
        for args in self._pending:
            fallback.add_route(*args)
        self._active_router = fallback

    def match(
            self,
            path: str,
            method: Method | None = None,
    ) -> tuple[ASGIAppType, RouteHandlerType, dict[str, str], str] | None:
        """ Delegate to the active router. """
        if self._active_router is None:
            self.construct()
        return self._active_router.match(path=path, method=method)

    def clear(self) -> None:
        """ Reset all state. """
        for r in self.routers:
            r.clear()
        self._active_router = None
        self._analysis = None
        self._pending.clear()
        self._route_count = 0

    def _rank_routers(self, analysis: RouteAnalysis) -> list[BaseRouter]:
        regexp: BaseRouter | None = None
        trie: BaseRouter | None = None
        for r in self.routers:
            if isinstance(r, RegExpRouter) and regexp is None:
                regexp = r
            elif isinstance(r, TrieRouter) and trie is None:
                trie = r

        if regexp is None or trie is None:
            return list(self.routers)

        if analysis.static_ratio == 1.0:
            return [regexp, trie]

        if analysis.has_overlapping_params:
            return [trie, regexp]

        if analysis.dynamic_ratio <= 0.30:
            return [regexp, trie]

        if analysis.dynamic_ratio > 0.70:
            return [trie, regexp]

        return [trie, regexp]

    def __len__(self) -> int:
        return self._route_count
