from speedy.types import Receive, Scope, Send


class Speedy:
    def __init__(self) -> None: ...

    def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = self

    def get(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def put(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def post(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def delete(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def options(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def head(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def path(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def trace(self) -> None:
        # TODO: add decoration HTTPHandler
        ...

    def websocket(self) -> None:
        # TODO: add decoration WebSocket
        ...

    def exception_handler(self) -> None:
        # TODO: add decoration ExceptionHandler
        ...

    def middleware(self) -> None:
        # TODO: add decoration Middleware
        ...
