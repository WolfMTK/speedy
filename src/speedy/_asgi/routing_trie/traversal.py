from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, TYPE_CHECKING

from speedy._asgi.routing_trie.types import ASGIHandlerTuple, PathParameterSentinel
from speedy.exceptions import NotFoundException, MethodNotAllowedException
from speedy.types import Method, ASGIAppType, RouteHandlerType, PathParameterDefinition
from speedy.utils import normalize_path

if TYPE_CHECKING:
    from speedy._asgi.routing_trie import RouteTrieNode


def parse_path_to_route(
        method: Method | None,
        mount_paths_regex: re.Pattern | None,
        mount_routes: dict[str, RouteTrieNode],
        path: str,
        plain_routes: set[str],
        root_node: RouteTrieNode,
) -> tuple[ASGIAppType, RouteHandlerType, str, dict[str, Any], str]:
    """ Resolves a request path to a route handler, mount point, or traversal result. """
    try:
        if path in plain_routes:
            asgi_app, handler = parse_node_handlers(node=root_node.children[path], method=method)
            return asgi_app, handler, path, {}, path

        if mount_paths_regex and (match := mount_paths_regex.match(path)):
            mount_path = path[: match.end()]
            mount_node = mount_routes[mount_path]
            remaining_path = path[match.end():]

            if not _is_sub_route_match(remaining_path, mount_node, mount_path):
                asgi_app, handler = parse_node_handlers(node=mount_node, method=method)
                final_path = f"{remaining_path.rstrip('/')}/"
                return asgi_app, handler, final_path, {}, root_node.path_template

        node, path_parameters, path = traverse_route_map(
            root_node=root_node,
            path=path,
        )
        asgi_app, handler = parse_node_handlers(node=node, method=method)
        key = method or ("asgi" if node.is_asgi else "websocket")
        parsed_path_parameters = parse_path_params(
            node.path_parameters[key],
            tuple(path_parameters),
        )

        return (
            asgi_app,
            handler,
            path,
            parsed_path_parameters,
            node.path_template,
        )

    except ValueError as e:
        raise NotFoundException() from e


def parse_node_handlers(
        node: RouteTrieNode,
        method: Method | None
) -> ASGIHandlerTuple:
    """ Retrieves the ASGI handler and application from a route node. """
    handlers = node.asgi_handlers

    if node.is_asgi:
        return handlers["asgi"]
    if method:
        try:
            return handlers[method]
        except KeyError as e:
            raise MethodNotAllowedException(headers={"allow": ", ".join(handlers)}) from e
    return handlers["websocket"]


def traverse_route_map(
        root_node: RouteTrieNode,
        path: str
) -> tuple[RouteTrieNode, list[str], str]:
    """ Traverses the route trie to find the matching node for a given path. """
    current_node = root_node
    path_params: list[str] = []
    path_components = list(filter(None, path.split("/")))

    for i, component in enumerate(path_components):
        if component in current_node.child_keys:
            current_node = current_node.children[component]
            continue

        if current_node.is_path_param_node:
            is_path_type = current_node.is_path_type
            current_node = current_node.children[PathParameterSentinel]

            if is_path_type:
                path_params.append(normalize_path("/".join(path_components[i:])))
                break

            path_params.append(component)
            continue

        raise NotFoundException()

    if not current_node.asgi_handlers:
        raise NotFoundException()

    return current_node, path_params, path


@lru_cache(1024)
def parse_path_params(
        parameter_definitions: tuple[PathParameterDefinition, ...],
        path_param_values: tuple[str, ...],
) -> dict[str, Any]:
    """ Parses string path parameters into their corresponding types. """
    return {
        param_definition.name: parser(value) if (parser := param_definition.parser) else value
        for param_definition, value in zip(parameter_definitions, path_param_values)
    }


def _is_sub_route_match(
        remaining_path: str,
        mount_node: RouteTrieNode,
        mount_path: str
) -> bool:
    if not remaining_path:
        return False

    return any(
        remaining_path.startswith(f"{sub_route}/")
        for sub_route in mount_node.children
        if sub_route != mount_path and isinstance(sub_route, str)
    )
