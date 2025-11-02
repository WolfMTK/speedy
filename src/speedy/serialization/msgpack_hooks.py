from typing import Callable, Any

from speedy.exceptions.base import SerializationException
from speedy.serialization.base import default_serializer


def encode_msgpack(value: Any, serializer: Callable[[Any], Any] | None = None) -> bytes:
    """ Encode a value into MessagePack. """
    import msgpack

    try:
        return msgpack.packb(
            value,
            default=lambda obj: serializer(obj) if serializer else default_serializer(obj),
            use_bin_type=True,
        )
    except (TypeError, ValueError) as err:
        raise SerializationException(f"Unable to serialize value {type(value)}: {err}") from err
