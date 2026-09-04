from enum import StrEnum


class HTTPMethod(str, StrEnum):
    """An enum for HTTP methods."""

    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"


class ScopeType(str, StrEnum):
    """An enum for the 'http' key stored under Scoped."""

    HTTP = "http"
    WEBSOCKET = "websocket"
    LIFESPAN = "lifespan"
