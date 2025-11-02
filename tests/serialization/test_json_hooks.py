import json
from datetime import datetime
from unittest.mock import patch

import pytest

from speedy.exceptions.base import SerializationException
from speedy.serialization import encode_json

DATETIME = datetime(2023, 10, 1, 12, 0, 0)


@pytest.mark.parametrize(
    "cases", [
        ({"key": "value"}, b'{"key":"value"}'),
        ([1, 2, 3], b'[1,2,3]'),
        ("hello", b'"hello"'),
        (42, b'42'),
        (3.14, b'3.14'),
        (True, b'true'),
        (None, b'null'),
    ],
)
def test_encode_builtin_types(
        cases: dict[str, str] | list[int] | str | int | float | bool | None,
) -> None:
    value, expected = cases
    result = encode_json(value)
    assert result == expected
    assert json.loads(result) == value


def test_encode_with_custom_serializer() -> None:
    def custom_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError()

    result = encode_json(DATETIME, serializer=custom_serializer)
    expected = json.dumps(DATETIME.isoformat(), ensure_ascii=False).encode("utf-8")
    assert result == expected


def test_unsupported_type_without_serializer() -> None:
    class UnsupportedType:
        pass

    with pytest.raises(SerializationException) as exc_info:
        encode_json(UnsupportedType())
    str(exc_info.value)
    assert "Unsupported type" in str(exc_info.value)


def test_json_library_errors() -> None:
    with patch("json.dumps", side_effect=OverflowError("Number too large")):
        with pytest.raises(SerializationException) as exc_info:
            encode_json(0)

    assert "Number too large" in str(exc_info.value)


def test_utf8_encoding() -> None:
    value = "Hello, world!"
    result = encode_json(value)
    assert json.loads(result) == value
    json_string = result.decode("utf-8")
    assert "Hello" in json_string
