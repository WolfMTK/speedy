import json
from typing import Any, Callable

from speedy.exceptions.base import SerializationException
from speedy.serialization.base import default_serializer


def encode_json(value: Any, serializer: Callable[[Any], Any] | None = None) -> bytes:
    """ Encode a value into JSON. """
    try:
        json_str = json.dumps(
            value,
            default=lambda obj: serializer(obj) if serializer else default_serializer(obj),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return json_str.encode("utf-8")
    except (TypeError, ValueError, OverflowError) as err:
        raise SerializationException(str(err)) from err
