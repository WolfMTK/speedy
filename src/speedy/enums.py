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
    LIFESPAN = 'lifespan'


class MediaTextType(StrEnum):
    PLAIN = 'text/plain'


class WebSocketState(StrEnum):
    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    DISCONNECTED = 'disconnected'
    RESPONSE = 'response'


class WebSocketStatusEvent(StrEnum):
    START = 'websocket.http.response.start'
    SEND = 'websocket.http.send'
    SEND_EVENT = 'websocket.send'
    ACCEPT = 'websocket.accept'
    BODY = 'websocket.http.response.body'
    CLOSE = 'websocket.close'
    CONNECT = 'websocket.connect'
    RECEIVE = 'websocket.receive'
    DISCONNECT = 'websocket.disconnect'


class WebSocketEncoding(StrEnum):
    TEXT = 'text'
    BYTES = 'bytes'
    JSON = 'json'
