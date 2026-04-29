from enum import Enum


class HTTPMethod(str, Enum):
    """An enum for HTTP methods."""
    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"
