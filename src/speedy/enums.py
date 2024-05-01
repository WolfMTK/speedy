from enum import StrEnum


class HttpMethod(StrEnum):
    GET = 'GET'
    POST = 'POST'
    DELETE = 'DELETE'
    PATCH = 'PATCH'
    PUT = 'PUT'
    HEAD = 'HEAD'
    TRACE = 'TRACE'
    OPTIONS = 'OPTIONS'


class ScopeType(StrEnum):
    HTTP = 'http'
    WEBSOCKET = 'websocket'


class MediaTextType(StrEnum):
    PLAIN = 'text/plain'


class WebSocketEncoding(StrEnum):
    TEXT = 'text'
    BYTES = 'bytes'
    JSON = 'json'
