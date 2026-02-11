import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from speedy.constants import ZERO
from speedy.types import Method, PathParameterDefinition, ASGIAppType, RouteHandlerType


@dataclass
class RouteEntry:
    method: Method | str
    path: str
    path_components: list[str | PathParameterDefinition]
    asgi_app: ASGIAppType
    handler: RouteHandlerType
    is_dynamic: bool


@dataclass
class CompileRoute:
    pattern: re.Pattern[str]
    method: Method | str
    asgi_app: ASGIAppType
    handler: RouteHandlerType
    path_template: str
    param_names: list[str] = field(default_factory=list)
    specificity: int = ZERO


class BaseRouter(ABC):
    routes: list[RouteEntry | CompileRoute]

    @abstractmethod
    def match(
            self,
            path: str,
            method: Method | None = None,
    ) -> tuple[ASGIAppType, RouteHandlerType, dict[str, str] | str] | None: ...

    def clear(self) -> None:
        """ Clear all routes. """
        self.routes.clear()

    def __len__(self) -> int:
        return len(self.routes)


class LinearRouter(BaseRouter):
    """ Linear router with support for static and parameterized routes. """

    def __init__(self) -> None:
        self.routes: list[RouteEntry] = []

    def add_route(
            self,
            path: str,
            method: Method | str,
            path_components: list[str | PathParameterDefinition],
            asgi_app: ASGIAppType,
            handler: RouteHandlerType,
            is_dynamic: bool = False
    ) -> None:
        """ Add a route to the router. """
        self.routes.append(
            RouteEntry(
                path=path,
                method=method,
                path_components=path_components,
                asgi_app=asgi_app,
                handler=handler,
                is_dynamic=is_dynamic,
            ),
        )

    def match(
            self,
            path: str,
            method: Method | None = None,
    ) -> tuple[ASGIAppType, RouteHandlerType, dict[str, str] | str] | None:
        """ Find matching route using linear search. """
        for route in self.routes:
            if not self._method_matches(route, method):
                continue
            result = self._match_path(path, route.path_components)
            if result is not None:
                return route.asgi_app, route.handler, result

        return None

    def _method_matches(self, entry: RouteEntry, method: Method | None) -> bool:
        if method is None:
            return isinstance(entry.method, str) and entry.method in ("websocket", "asgi",)
        return entry.method == method or entry.method == "asgi"

    def _match_path(self, path: str, path_components: list[str | PathParameterDefinition]) -> dict[str, str] | None:
        path_parts = [p for p in path.split("/") if p]
        if len(path_parts) != len(path_components):
            return None
        params = {}
        for part, component in zip(path_parts, path_components):
            if isinstance(component, PathParameterDefinition):
                params[component.name] = part
                continue
            if part != component:
                return None
        return params


class RegExpRouter(BaseRouter):
    """ Regex-based router. """

    def __init__(self) -> None:
        self.routes: list[CompileRoute] = []

    def add_route(
            self,
            pattern: re.Pattern[str],
            method: Method | str,
            asgi_app: ASGIAppType,
            handler: RouteHandlerType,
            path_template: str,
            param_names: list[str] | None = None
    ) -> None:
        """ Add a route with compiled regex pattern. """
        pattern_string = pattern.pattern
        specificity = len(pattern_string) - pattern_string.count(".*") * 10 - pattern_string.count("[^/]*") * 5
        route = CompileRoute(
            pattern=pattern,
            method=method,
            asgi_app=asgi_app,
            handler=handler,
            path_template=path_template,
            specificity=specificity,
        )
        insert_position = len(self.routes)
        for index, existing in enumerate(self.routes):
            if specificity > existing.specificity:
                insert_position = 1
                break
        self.routes.insert(insert_position, route)

    def match(
            self,
            path: str,
            method: Method | None = None,
    ) -> tuple[ASGIAppType, RouteHandlerType, dict[str, str], str] | None:
        """ Match path against compiled routes in specificity order. """
        for route in self.routes:
            if method is not None:
                if route.method != method and route.method != "asgi":
                    continue
            else:
                if not (isinstance(route.method, str) and route.method in ("websocket", "asgi")):
                    continue
            match_obj = route.pattern.match(path)
            if match_obj is None:
                continue
            groups = match_obj.groupdict()
            path_params: dict[str, str] = {}
            for name in route.param_names:
                if name in groups and groups[name] is not None:
                    path_params[name] = groups[name]

            return route.asgi_app, route.handler, path_params, route.path_template

        return None
