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
