from speedy.status_code import WS_1000_NORMAL_CLOSURE


class RuntimeWebSocketException(Exception):
    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return f'{type(self).__name__}(message={self.message})'


class WebSocketDisconnect(Exception):
    def __init__(
            self,
            code: int = WS_1000_NORMAL_CLOSURE,
            reason: str | None = None
    ) -> None:
        self.code = code
        self.reason = reason or ''
