import json
from collections import deque
from collections.abc import Callable, Mapping
from datetime import datetime, date, time
from decimal import Decimal
from ipaddress import IPv4Address, IPv4Interface, IPv4Network, IPv6Address, IPv6Interface, IPv6Network
from pathlib import Path, PurePath
from re import Pattern
from typing import Any
from uuid import UUID

from speedy.datastructures import SecretBytes, SecretString, ImmutableState
from speedy.exceptions.base import SerializationException
from speedy.types import TypeEncodersMap
from speedy.types.composite_types import TypeDecodersSequence
from speedy.utils.typing import get_origin_or_inner_type

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
        type_encoders: Mapping[Any, Callable[[Any], Any]] | None = None,
) -> Any:
    """ Transform values non-natively supported by `msgspec`. """
    type_encoders = {**DEFAULT_TYPE_ENCODERS, **(type_encoders or {})}
    for base in value.__class__.__mro__[:-1]:
        try:
            encoder = type_encoders[base]
        except KeyError:
            continue
        else:
            return encoder
    raise TypeError(f"Unsupported type: {type(value)}")


def default_deserializer(
        target_type: Any, value: Any, type_decoders: TypeDecodersSequence | None = None,
) -> Any:
    """ Transform values non-natively supported by `msgspec`. """
    runtime_type = get_origin_or_inner_type(target_type) or target_type

    if isinstance(value, runtime_type):
        return value

    if type_decoders:
        for predicate, decoder in type_decoders:
            if predicate(target_type):
                return decoder(target_type, value)

    if type_decoders:
        for predicate, decoder in type_decoders:
            if predicate(target_type):
                return decoder(target_type, value)

    if issubclass(target_type, (PurePath, ImmutableState, UUID)):
        return target_type(value)

    if issubclass(target_type, SecretBytes) and isinstance(value, (bytes, str)):
        return SecretBytes(value.encode("utf-8") if isinstance(value, str) else value)

    if issubclass(target_type, SecretString) and isinstance(value, str):
        return SecretString(value)

    raise TypeError(f"Unsupported type: {type(value)!r}")


def encode_json(value: Any, serializer: Callable[[Any], Any] | None = None) -> bytes:
    """ Encode a value into JSON. """
    try:
        def _adapter_encode(value: Any) -> Any:
            if serializer is not None:
                try:
                    return serializer(value) if serializer else default_serializer(value)
                except (TypeError, ValueError, AttributeError):
                    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
            raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

        json_str = json.dumps(value, default=_adapter_encode, ensure_ascii=False, separators=(",", ":"))
        return json_str.encode("utf-8")
    except (TypeError, ValueError, OverflowError) as err:
        raise SerializationException(str(err)) from err


def encode_msgpack(value: Any, serializer: Callable[[Any], Any] | None):
    ...
