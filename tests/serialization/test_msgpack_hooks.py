from datetime import datetime

import msgpack
import pytest

from speedy.exceptions.base import SerializationException
from speedy.serialization import encode_msgpack

DATETIME = datetime(2023, 10, 1, 12, 0, 0)


@pytest.mark.parametrize(
    "cases", [
        ({"key": "value"}, {"key": "value"}),
        ([1, 2, 3], [1, 2, 3]),
        ("hello", "hello"),
        (42, 42),
        (3.14, 3.14),
        (True, True),
        (None, None),
        (b"raw_bytes", b"raw_bytes"),
    ],
)
def test_encode_builtin_types(cases: dict[str, str] | list[int] | str | int | float | bool | None | bytes) -> None:
    value, expected = cases
    encoded = encode_msgpack(value)
    decoded = msgpack.unpackb(encoded, raw=False)
    assert decoded == expected


def test_encode_with_custom_serializer():
    def custom_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError()

    encoded = encode_msgpack(DATETIME, serializer=custom_serializer)
    decoded = msgpack.unpackb(encoded, raw=False)
    assert decoded == DATETIME.isoformat()


def test_unsupported_type_without_serializer():
    class UnsupportedType:
        pass

    with pytest.raises(SerializationException) as exc_info:
        encode_msgpack(UnsupportedType())

    assert "Unable to serialize" in str(exc_info.value)


def test_serializer_fails():
    def failing_serializer(obj):
        raise ValueError("I don't know how to serialize this!")

    with pytest.raises(SerializationException) as exc_info:
        encode_msgpack(DATETIME, serializer=failing_serializer)

    assert "I don't know how to serialize this!" in str(exc_info.value)
