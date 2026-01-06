from __future__ import annotations

import collections
import re
from traceback import format_exc
from typing import TYPE_CHECKING

from speedy._asgi.routing_trie import RouteTrieNode, create_node, validate_node
from speedy.routes import HTTPRoute, WebSocketRoute, ASGIRoute
from speedy.routes.base import BaseRoute
from speedy.types import (
    LifeSpanReceive,
    LifeSpanSend,
    LifespanShutdownCompleteEvent,
    LifespanStartupCompleteEvent,
    LifespanStartupFailedEvent,
    LifespanShutdownFailedEvent,
    Scope,
    Receive,
    Send,
    ExceptionHandlersMap,
)

if TYPE_CHECKING:
    from speedy import Speedy


class ASGIRouter:
    """ Speedy ASGI router. """

    def __init__(self, app: Speedy) -> None:
        self._app_exception_handlers: ExceptionHandlersMap = app.exception_handlers
        self._trie_initialized = False
        self._mount_paths_regex: re.Pattern | None = None
        self._mount_routes: dict[str, RouteTrieNode] = {}
        self._plain_routes: set[str] = set()
        self._registered_routes: set[HTTPRoute | WebSocketRoute | ASGIRoute] = set()
        self.app = app
        self.root_route_map_node: RouteTrieNode = create_node()
        self.route_handler_index: dict[str, RouteTrieNode] = {}
        self.route_mapping: dict[str, list[BaseRoute]] = collections.defaultdict(list)

    async def lifespan(self, receive: LifeSpanReceive, send: LifeSpanSend) -> None:
        """ Handle the ASGI `lifespan` event on application startup and shutdown. """
        startup_event: LifespanStartupCompleteEvent = {"type": "lifespan.startup.complete"}
        shutdown_event: LifespanShutdownCompleteEvent = {"type": "lifespan.shutdown.complete"}

        await receive()
        started = False
        try:
            async with self.app.lifespan():
                await send(startup_event)
                started = True
                await receive()
        except BaseException as e:
            formatted_exception = format_exc()

            if started:
                fail_message: LifespanShutdownFailedEvent = {
                    "type": "lifespan.shutdown.failed",
                    "message": formatted_exception,
                }
            else:
                fail_message: LifespanStartupFailedEvent = {
                    "type": "lifespan.startup.failed",
                    "message": formatted_exception,
                }

            await send(fail_message)
            raise e

        await send(shutdown_event)

    def construct_routing_trie(self) -> None:
        """ Create a map of the app's routes. """
        if self._trie_initialized:
            self._mount_paths_regex = None
            self._mount_routes = {}
            self._plain_routes = set()
            self._registered_routes = set()
            self.root_route_map_node = create_node()
            self.route_handler_index = {}
            self.route_mapping = collections.defaultdict(list)

        validate_node(node=self.root_route_map_node)
        if self._mount_routes:
            self._mount_paths_regex = re.compile("|".join(sorted(set(self._mount_routes))))
