from typing import Protocol, Any


class HTTPGet(Protocol):
    def get(self, *args: Any, **kwargs: Any) -> Any: ...


class HTTPPost(Protocol):
    def post(self, *args: Any, **kwargs: Any) -> Any: ...


class HTTPDelete(Protocol):
    def delete(self, *args: Any, **kwargs: Any) -> Any: ...


class HTTPPatch(Protocol):
    def patch(self, *args: Any, **kwargs: Any) -> Any: ...


class HTTPPut(Protocol):
    def put(self, *args: Any, **kwargs: Any) -> Any: ...


class HTTPHead(Protocol):
    def head(self, *args: Any, **kwargs: Any) -> Any: ...


class HTTPTrace(Protocol):
    def trace(self, *args: Any, **kwargs: Any) -> Any: ...


class HTTPOptions(Protocol):
    def options(self, *args: Any, **kwargs: Any) -> Any: ...


# TODO: add specific arguments when implementing an application class
class BaseHTTPMethods(
    HTTPGet,
    HTTPPost,
    HTTPDelete,
    HTTPPatch,
    HTTPPut,
    HTTPHead,
    HTTPTrace,
    HTTPOptions
):
    pass
