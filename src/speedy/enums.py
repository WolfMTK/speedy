from enum import StrEnum


class HttpMethod(StrEnum):
    """ An enum for HTTP methods. """

    GET = 'GET'
    POST = 'POST'
    DELETE = 'DELETE'
    PATCH = 'PATCH'
    PUT = 'PUT'
    HEAD = 'HEAD'
    TRACE = 'TRACE'
    OPTIONS = 'OPTIONS'


class ScopeType(StrEnum):
    """ An enum for the 'http' key stored under Scoped. """

    HTTP = 'http'
    WEBSOCKET = 'websocket'
    LIFESPAN = 'lifespan'


class MediaType(StrEnum):
    """ An enum for content-type header values. """

    JSON = 'application/json'
    XML = 'application/xml'
    HTML = 'text/html'
    TEXT = 'text/plain'
    CSS = 'text/css'
    MESSAGEPACK = 'application/x-msgpack'
