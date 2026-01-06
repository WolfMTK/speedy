from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

from speedy.exceptions.http_exceptions import ImproperlyConfiguredException

if TYPE_CHECKING:
    from speedy._asgi.routing_trie import RouteTrieNode


def validate_node(node: RouteTrieNode) -> None:
    """ Recursively traverses the trie from the given node upwards. """
    if node.is_asgi and any(key != "asgi" for key in node.asgi_handlers):
        raise ImproperlyConfiguredException(
            "ASGI handlers must have a unique path not shared by other route handler",
        )

    if node.is_mount and node.children and any(
            itertools.chain.from_iterable(
                child.path_parameters.values()
                if isinstance(child.path_parameters, dict)
                else child.path_parameters
                for child in node.children.values()
            )
    ):
        raise ImproperlyConfiguredException(
            "Path parameters are not allowed under a static or mount route.",
        )

    for child in node.children.values():
        if child is node:
            continue
        validate_node(node=child)
