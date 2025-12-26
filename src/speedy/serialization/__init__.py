from speedy.serialization.base import get_serializer
from speedy.serialization.json_hooks import encode_json
from speedy.serialization.msgpack_hooks import encode_msgpack

__all__ = (
    "encode_json",
    "encode_msgpack",
    "get_serializer",
)
