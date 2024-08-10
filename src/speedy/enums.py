from enum import Enum


class HttpMethod(str, Enum):
    """ An enum for HTTP methods. """

    GET = 'GET'
    POST = 'POST'
    DELETE = 'DELETE'
    PATCH = 'PATCH'
    PUT = 'PUT'
    HEAD = 'HEAD'
    TRACE = 'TRACE'
    OPTIONS = 'OPTIONS'


class ScopeType(str, Enum):
    """ An enum for the 'http' key stored under Scoped. """

    HTTP = 'http'
    WEBSOCKET = 'websocket'
    LIFESPAN = 'lifespan'


class MediaType(str, Enum):
    """ An enum for content-type header values. """

    JSON = 'application/json'
    XML = 'application/xml'
    HTML = 'text/html'
    TEXT = 'text/plain'
    CSS = 'text/css'
    MESSAGEPACK = 'application/x-msgpack'


class Match(int, Enum):
    NONE = 0
    PARTIAL = 1
    FULL = 2
