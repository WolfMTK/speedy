import re
from abc import ABC
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Self, Pattern

from speedy.connection.websockets import WebSocketClose
from speedy.datastructures.url import URLPath
from speedy.exceptions.base import ConvertorTypeException
from speedy.response import PlainTextResponse
from speedy.status_code import HTTP_404_NOT_FOUND, WS_1000_NORMAL_CLOSURE
from speedy.types import Scope
from speedy.types.asgi_types import (
    ASGIReceiveCallable,
    ASGISendCallable
)
from speedy.utils.convertors import CONVERTOR_TYPES, Convertor


class Match(IntEnum):
    NONE = 0
    PARTIAL = 1
    FULL = 2


class BaseRoute(ABC):
    async def __call__(self,
                       scope: Scope,
                       receive: ASGIReceiveCallable,
                       send: ASGISendCallable):
        match, child_scope = self.matches(scope)

        match Match:
            case Match.NONE:
                if scope['type'] == 'http':
                    await self._send_response_not_found(scope, receive, send)
                elif scope['type'] == 'websocket':
                    await self._close_websocket(scope, receive, send)
            case _:
                scope.update(child_scope)
                await self.handle(scope, receive, send)

    def matches(self, scope: Scope) -> tuple[Match, Scope]:
        ...

    def url_path_for(self, name: str, **params: Any) -> URLPath:
        ...

    async def handle(self,
                     scope: Scope,
                     receive: ASGIReceiveCallable,
                     send: ASGISendCallable) -> None:
        ...

    async def _send_response_not_found(self,
                                       scope: Scope,
                                       receive: ASGIReceiveCallable,
                                       send: ASGISendCallable) -> None:
        response = PlainTextResponse('Not Found', status_code=HTTP_404_NOT_FOUND)
        await response(scope, receive, send)

    async def _close_websocket(
            self,
            scope: Scope,
            receive: ASGIReceiveCallable,
            send: ASGISendCallable
    ) -> None:
        websocket_close = WebSocketClose(WS_1000_NORMAL_CLOSURE)
        await websocket_close(scope, receive, send)


@dataclass
class Path:
    path_regex: Pattern[str]
    path_format: str
    param_convertors: dict[str, Any]


PARAM_REGEX = re.compile("{([a-zA-Z_][a-zA-Z0-9_]*)(:[a-zA-Z_][a-zA-Z0-9_]*)?}")


class CompilePath:
    _path: Path

    def __new__(cls, path: str) -> Self:
        instance = super().__new__(cls)
        path_regex, path_format, param_convertors = instance._compile_path(path)
        instance._path = Path(
            path_regex=path_regex,
            path_format=path_format,
            param_convertors=param_convertors
        )
        return instance

    @property
    def path_regex(self) -> Pattern[str]:
        return self._path.path_regex

    @property
    def path_format(self) -> str:
        return self._path.path_format

    @property
    def param_convertors(self) -> dict[str, Any]:
        return self._path.param_convertors

    def _compile_path(self, path: str) -> tuple[Pattern[str], str, dict[str, Convertor[Any]]]:
        is_host = not path.startswith('/')

        path_regex = '^'
        path_format = ''
        duplicated_params = set()

        index = 0
        param_convertors = dict()

        for match in PARAM_REGEX.finditer(path):
            param_name, convertor_type = match.groups('str')
            convertor = self._get_convertor(convertor_type)

            path_regex += re.escape(path[index: match.start()])
            path_regex += f'(?P<{param_name}>{convertor.regex})'

            path_format += path[index: match.start()]
            path_format += f'{param_name}'

            self._add_duplicated_params(duplicated_params, param_convertors, param_name)
            param_convertors[param_name] = convertor
            index = match.end()

        self._check_duplicated_params(duplicated_params, path)

        path_regex = self._correct_path_regex(index, is_host, path, path_regex)
        path_format += path[index:]
        return re.compile(path_regex), path_format, param_convertors

    def _correct_path_regex(self, index: int, is_host: bool, path: str, path_regex: str) -> str:
        if is_host:
            hostname = path[index:].split(':')[0]
            path_regex += re.escape(hostname) + '$'
        else:
            path_regex += re.escape(path[index:]) + '$'
        return path_regex

    def _check_duplicated_params(self, duplicated_params: set[str], path: str) -> None:
        if duplicated_params:
            names = ', '.join(sorted(duplicated_params))
            ending = 's' if len(duplicated_params) > 1 else ''
            raise ValueError(f'Duplicated param name{ending} {names} at path {path}')

    def _add_duplicated_params(self,
                               duplicated_params: set[str],
                               param_convertors: dict[str, Convertor[Any]],
                               param_name: str) -> None:
        if param_name in param_convertors:
            duplicated_params.add(param_name)

    def _get_convertor(self, convertor_type: str) -> Convertor[Any]:
        convertor_type = convertor_type.lstrip(':')
        if convertor_type not in CONVERTOR_TYPES:
            raise ConvertorTypeException(f'Unknown path convertor "{convertor_type}"')
        convertor = CONVERTOR_TYPES[convertor_type]
        return convertor
