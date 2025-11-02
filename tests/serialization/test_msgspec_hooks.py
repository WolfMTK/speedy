import json
from collections import deque
from datetime import datetime, date, time
from decimal import Decimal
from ipaddress import IPv4Address, IPv6Network
from pathlib import Path, PurePath
from re import compile as re_compile
from typing import Any
from unittest.mock import Mock, patch
from uuid import UUID

import msgpack
import pytest

from speedy.datastructures import SecretBytes, SecretString, ImmutableState
from speedy.exceptions.base import SerializationException
from speedy.serialization.msgspec_hooks import default_serializer, default_deserializer, encode_json, encode_msgpack

DATETIME = datetime(2023, 10, 1, 12, 0, 0)


@pytest.mark.parametrize(
    "cases", (
            (Path("/tmp"), str),
            (PurePath("/tmp"), str),
            (IPv4Address("192.168.0.1"), str),
            (IPv6Network("2001:db8::/32"), str),
            (datetime(2025, 10, 29, 12, 0), lambda v: v.isoformat()),
            (date(2025, 10, 29), lambda v: v.isoformat()),
            (time(12, 30), lambda v: v.isoformat()),
            (deque([1, 2, 3]), list),
            (
                    Decimal("123"),
                    lambda v: int(v) if v.as_tuple().exponent >= 0 else float(
                        v,
                    ),
            ),
            (re_compile(r"\d+"), lambda v: v.pattern),
            (
                    SecretBytes(b"secret"),
                    lambda v: v.get_obscured().decode("utf-8"),
            ),
            (SecretString("password"), lambda v: v.get_obscured()),
            ("hello", str),
            (42, int),
            (3.14, float),
            ({1, 2, 3}, set),
            (frozenset([1, 2]), frozenset),
            (b"raw", bytes),
    ),
)
def test_default_serializer(cases: tuple[Any, str]) -> None:
    value, expected_encoder = cases
    encoder = default_serializer(value)
    assert callable(encoder)
    result = encoder(value)
    expected_result = expected_encoder(value)  # noqa
    assert result == expected_result


def test_default_serializer_with_custom_type_encoder() -> None:
    custom_encoder = {
        Path: lambda v: f"custom:{v}",
    }
    encoder = default_serializer(Path("foo"), type_encoders=custom_encoder)
    assert encoder(Path("/foo")) == "custom:/foo" or encoder(Path("/foo")) == "custom:\\foo"


def test_default_serializer_unsupported_type_encoders() -> None:
    class UnsupportedTypeEncoder:
        pass

    with pytest.raises(TypeError, match="Unsupported type"):
        default_serializer(UnsupportedTypeEncoder())


@pytest.mark.parametrize(
    "value, expected",
    [
        ((str, "foo"), "foo"),
        ((int, 1), 1),
    ],
)
def test_value_already_correct_type(value: tuple[type[str, int], str], expected: str) -> None:
    typ, val = value
    assert default_deserializer(typ, val) == expected


def test_value_correct_type_after_unwrapping_generic() -> None:
    value = [1, 2, 3]
    assert default_deserializer(list[int], value) == value


@pytest.mark.parametrize(
    "typ, input_val, expected_str",
    [
        (PurePath, "/file.txt", "/file.txt"),  # PurePath может нормализовать слэши
        (UUID, "12345678-1234-5678-1234-567812345678", "12345678-1234-5678-1234-567812345678"),
        (ImmutableState, {"key": "value"}, {"key": "value"}),
    ],
)
def test_builtin_and_custom_types(typ, input_val, expected_str) -> None:
    result = default_deserializer(typ, input_val)
    assert isinstance(result, typ)
    if typ is PurePath:
        actual_str = str(result)
        assert actual_str == expected_str or actual_str == expected_str.replace("/", "\\")
    elif typ is UUID:
        assert str(result) == expected_str
    elif typ is ImmutableState:
        assert result.as_dict() == expected_str


@pytest.mark.parametrize(
    "secret_type, input_val, expected_secret",
    [
        (SecretBytes, b"secret", b"secret"),
        (SecretBytes, "secret", b"secret"),
        (SecretString, "secret", "secret"),
    ],
)
def test_secret_types(secret_type, input_val, expected_secret) -> None:
    result = default_deserializer(secret_type, input_val)
    assert isinstance(result, secret_type)
    assert result.get_secret_value() == expected_secret


def test_secret_string_from_bytes_fails() -> None:
    with pytest.raises(TypeError, match="Unsupported type"):
        default_deserializer(SecretString, b"secret")


def test_unsupported_type() -> None:
    class UnsupportedType:
        pass

    with pytest.raises(TypeError, match="Unsupported type"):
        default_deserializer(UnsupportedType, "value")


def test_no_matching_type_decoder() -> None:
    mock_predicate = Mock(return_value=False)
    mock_decoder = Mock()
    type_decoders = [(mock_predicate, mock_decoder)]
    uuid_str = "12345678-1234-5678-1234-567812345678"
    result = default_deserializer(UUID, uuid_str, type_decoders=type_decoders)
    mock_decoder.assert_not_called()
    assert isinstance(result, UUID)


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


def test_encode_msgpack_with_custom_serializer():
    def custom_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError()

    encoded = encode_msgpack(DATETIME, serializer=custom_serializer)
    decoded = msgpack.unpackb(encoded, raw=False)
    assert decoded == DATETIME.isoformat()


def test_unsupported_msgpack_type_without_serializer():
    class UnsupportedType:
        pass

    with pytest.raises(SerializationException) as exc_info:
        encode_msgpack(UnsupportedType())

    assert "Unable to serialize" in str(exc_info.value)


def test_serializer_msgpack_fails():
    def failing_serializer(obj):
        raise ValueError("I don't know how to serialize this!")

    with pytest.raises(SerializationException) as exc_info:
        encode_msgpack(DATETIME, serializer=failing_serializer)

    assert "I don't know how to serialize this!" in str(exc_info.value)
