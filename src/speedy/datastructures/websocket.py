from dataclasses import dataclass, field
from speedy.status_code import WS_1000_NORMAL_CLOSURE


@dataclass
class CloseWebSocket:
    type: str = 'websocket.close'
    code: int = WS_1000_NORMAL_CLOSURE
    reason: str = ''
