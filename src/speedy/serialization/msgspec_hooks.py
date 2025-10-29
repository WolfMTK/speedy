from collections import deque
from collections.abc import Callable, Mapping
from datetime import datetime, date, time
from decimal import Decimal
from ipaddress import IPv4Address, IPv4Interface, IPv4Network, IPv6Address, IPv6Interface, IPv6Network
from pathlib import Path, PurePath
from re import Pattern
from typing import Any

from speedy.datastructures import SecretBytes, SecretString
from speedy.types import TypeEncodersMap

DEFAULT_TYPE_ENCODERS: TypeEncodersMap = {
    Path: str,
    PurePath: str,
    IPv4Address: str,
    IPv4Interface: str,
    IPv4Network: str,
    IPv6Address: str,
    IPv6Interface: str,
    IPv6Network: str,
    datetime: lambda val: val.isoformat(),
    date: lambda val: val.isoformat(),
    time: lambda val: val.isoformat(),
    deque: list,
    Decimal: lambda val: int(val) if val.as_tuple().exponent >= 0 else float(val),
    Pattern: lambda val: val.pattern,
    SecretBytes: lambda val: val.get_obscured().decode("utf-8"),
    SecretString: lambda val: val.get_obscured(),
    str: str,
    int: int,
    float: float,
    set: set,
    frozenset: frozenset,
    bytes: bytes,
}


def default_serializer(
        value: Any,
        type_encoders: Mapping[Any, Callable[[Any], Any]] | None = None
) -> Any:
    """ Transform values non-natively supported by ```msgspec` """
    type_encoders = {**DEFAULT_TYPE_ENCODERS, **(type_encoders or {})}
    for base in value.__class__.__mro__[:-1]:
        try:
            encoder = type_encoders[base]
        except KeyError:
            continue
        else:
            return encoder
    raise TypeError(f"Unsupported type: {type(value)}")


def encode_msgpack(value: Any, serializer: Callable[[Any], Any] | None): ...


def encode_json(value: Any, serializer: Callable[[Any], Any] | None = None) -> bytes: ...
