from collections import deque
from datetime import datetime, date, time
from decimal import Decimal
from ipaddress import IPv4Address, IPv6Network
from pathlib import Path, PurePath
from re import compile as re_compile
from typing import Any

import pytest

from speedy.datastructures import SecretBytes, SecretString
from speedy.serialization.msgspec_hooks import default_serializer


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
    try:
        assert encoder(Path("/foo")) == "custom:/foo"
    except AssertionError:
        # Windows
        assert encoder(Path("/foo")) == "custom:\\foo"


def test_default_serializer_unsupported_type_encoders() -> None:
    class UnsupportedTypeEncoder:
        pass

    with pytest.raises(TypeError, match="Unsupported type"):
        default_serializer(UnsupportedTypeEncoder())
