from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple, Literal

from speedy.types import ASGIAppType, RouteHandlerType, Method, PathParameterDefinition


class PathParameterSentinel:
    """ Sentinel class designating a path parameter. """


class ASGIHandlerTuple(NamedTuple):
    """ Encapsulation of a route handler node. """

    asgi_app: ASGIAppType
    handler: RouteHandlerType


@dataclass(unsafe_hash=True)
class RouteTrieNode:
    """ A radix trie node. """

    asgi_handlers: dict[Method | Literal["websocket", "asgi"], ASGIHandlerTuple]
    child_keys: set[str | type[PathParameterSentinel]]
    children: dict[str | type[PathParameterSentinel], RouteTrieNode]
    is_path_param_node: bool
    is_path_type: bool
    is_asgi: bool
    is_mount: bool
    path_parameters: dict[Method | Literal["websocket", "asgi"], tuple[PathParameterDefinition],]
    path_template: str


def create_node() -> RouteTrieNode:
    return RouteTrieNode(
        asgi_handlers={},
        child_keys=set(),
        children={},
        is_path_param_node=False,
        is_asgi=False,
        is_mount=False,
        is_path_type=False,
        path_parameters={},
        path_template="",
    )
