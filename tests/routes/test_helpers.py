import datetime
import decimal
import pathlib
import uuid
from typing import Any

import pytest

from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.routes.helpers import (
    _validate_path_parameter,
    _parse_datetime,
    _parse_date,
    _parse_time,
    _parse_timedelta,
    _parse_path,
    TYPE_CONFIGS,
)
from speedy.types import PathParameterDefinition


@pytest.mark.parametrize(
    "param, path, expected",
    [
        ("id:int", "/{id:int}", ("id", "int")),
        (" id : int ", "/{id:int}", ("id", "int")),
        ("user_id:uuid ", "/{u}", ("user_id", "uuid")),
        ("start:date", "/{s}", ("start", "date")),
        ("file_path:path", "/{f}", ("file_path", "path")),
    ],
)
def test_validate_path_parameter_success(
        param: str,
        path: str,
        expected: tuple[str, str],
) -> None:
    assert _validate_path_parameter(param, path) == expected


@pytest.mark.parametrize("key_type", TYPE_CONFIGS.keys())
def test_validate_path_parameter_all_map_keys(key_type: Any) -> None:
    param_name = "param"
    param = f"{param_name}:{key_type}"
    path = f"/api/{{{param}}}"
    result = _validate_path_parameter(param, path)
    assert result[0] == param_name
    assert result[1] == key_type


@pytest.mark.parametrize(
    "param, path, msg_part",
    [
        ("id_int", "/users/{id_int}", "declared with a type"),
        (":int", "/{:int}", "length greater than zero"),
        ("   :int", "/{:int}", "length greater than zero"),
        ("id:", "/{id:}", "allowed type"),
        ("id:wrongtype", "/{id:wrongtype}", "allowed type"),
        ("id:int:extra", "/{id:int:extra}", "allowed type"),
    ],
)
def test_validate_path_parameter_raises(
        param: str,
        path: str,
        msg_part: str,
) -> None:
    with pytest.raises(ImproperlyConfiguredException) as exc_info:
        _validate_path_parameter(param, path)
    assert msg_part in str(exc_info.value)


@pytest.mark.parametrize(
    "value, expected",
    [
        (
                "1972-10-03T14:30:00",
                datetime.datetime(1972, 10, 3, 14, 30, 0),
        ),
        (
                "1972-10-03T14:30:00.123456",
                datetime.datetime(1972, 10, 3, 14, 30, 0, 123456),
        ),
        (
            "1972-10-03T14:30:00+03:00",
            datetime.datetime(
                1972, 10, 3, 14, 30, 0,
                tzinfo=datetime.timezone(datetime.timedelta(hours=3)),
            ),
        ),
    ],
)
def test_parse_datetime_valid_formats(
        value: str,
        expected: datetime.datetime,
) -> None:
    assert _parse_datetime(value) == expected


@pytest.mark.parametrize(
    "value, expected",
    [
        ("1972-10-03T14:30:00Z", 0),
        ("1972-10-03T14:30:00.123Z", 123000),
    ],
)
def test_parse_datetime_z_suffix_conversion(
        value: str,
        expected: int
) -> None:
    result = _parse_datetime(value)
    assert result.tzinfo is not None
    assert result.utcoffset().total_seconds() == 0
    assert result.microsecond == expected


def test_parse_datetime_invalid_format() -> None:
    with pytest.raises(ValueError):
        _parse_datetime("not-a-date")


@pytest.mark.parametrize(
    "value, expected", [("1972-10-03", datetime.date(1972, 10, 3))]
)
def test_parse_date_valid(value: str, expected: datetime.date) -> None:
    assert _parse_date(value) == expected


@pytest.mark.parametrize("value", ["1972/10/03", "1972-03-40"])
def test_parse_date_invalid_format(value: str) -> None:
    with pytest.raises(ValueError):
        _parse_date(value)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("15:45:30", datetime.time(15, 45, 30)),
        ("15:45:30.123456", datetime.time(15, 45, 30, 123456)),
    ],
)
def test_parse_time_valid(value: str, expected: datetime.time) -> None:
    assert _parse_time(value) == expected


@pytest.mark.parametrize("value", ["25:00:00"])
def test_parse_time_invalid_format(value: str) -> None:
    with pytest.raises(ValueError):
        _parse_time(value)


@pytest.mark.parametrize(
    "value, expected",
    [
        ("10", datetime.timedelta(seconds=10)),
        ("10.5", datetime.timedelta(seconds=10.5)),
        ("-10", datetime.timedelta(seconds=-10)),
    ],
)
def test_parse_timedelta_from_numeric_string(
        value: str,
        expected: datetime.timedelta
) -> None:
    assert _parse_timedelta(value) == expected
    assert _parse_timedelta(value).total_seconds() == expected.total_seconds()


@pytest.mark.parametrize(
    "value, expected",
    [
        ("01:00:00", datetime.timedelta(hours=1)),
        ("01:02:03", datetime.timedelta(hours=1, minutes=2, seconds=3)),
        ("00:00:01.500", datetime.timedelta(seconds=1, microseconds=500000)),
    ],
)
def test_parse_timedelta_from_time_format(
        value: str,
        expected: datetime.timedelta,
) -> None:
    assert _parse_timedelta(value) == expected


@pytest.mark.parametrize("value", ["invalid_string", "PT1M"])
def test_parse_timedelta_invalid_formats(value: str) -> None:
    with pytest.raises(ValueError) as exc_info:
        _parse_timedelta(value)
    assert "Invalid timedelta format" in str(exc_info.value)


def test_parse_path_static_structure() -> None:
    path = "/api/v1/users"
    p, fmt, components, params = _parse_path(path)
    assert p == "/api/v1/users"
    assert fmt == "/api/v1/users"
    assert components == ["api", "v1", "users"]
    assert params == {}


def test_parse_path_params_structure() -> None:
    path = "/users/{user_id:int}/posts/{post_uuid:uuid}"
    _, fmt, components, params = _parse_path(path)
    assert fmt == "/users/{user_id}/posts/{post_uuid}"
    assert len(params) == 2
    assert isinstance(components[1], PathParameterDefinition)
    assert isinstance(components[3], PathParameterDefinition)
    assert params["user_id"].type == int
    assert params["post_uuid"].type == uuid.UUID


def test_parse_path_parser_types() -> None:
    path = "/{s:str}/{i:int}/{f:float}/{d:decimal}/{u:uuid}/{td:timedelta}/{dt:datetime}/{p:path}"
    _, _, components, params = _parse_path(path)

    assert params["s"].parser is None
    assert params["s"].type == str

    assert params["p"].parser is None
    assert params["p"].type == pathlib.Path

    assert params["i"].parser == int
    assert params["i"].type == int

    assert params["f"].parser == float
    assert params["f"].type == float

    assert params["d"].parser == decimal.Decimal
    assert params["d"].type == decimal.Decimal

    assert params["u"].parser == uuid.UUID

    assert params["td"].parser == _parse_timedelta
    assert params["td"].type == datetime.timedelta

    assert params["dt"].parser == _parse_datetime
    assert params["dt"].type == datetime.datetime


def test_parse_path_edge_cases() -> None:
    path = "/users/{ id : int }"
    p, fmt, components, params = _parse_path(path)
    assert "id" in params
    assert params["id"].name == "id"
    assert params["id"].type == int
    assert fmt == "/users/{id}"


@pytest.mark.parametrize(
    "path, msg_part",
    [
        ("/items/{idint}", "declared with a type"),
        ("/items/{:int}", "length greater than zero"),
        ("/items/{id:wrong}", "allowed type"),
        ("/{id:int}/prefix/{id:int}", "Duplicate parameter"),
    ],
)
def test_parse_path_validation_errors(path: str, msg_part: str) -> None:
    with pytest.raises(ImproperlyConfiguredException) as exc_info:
        _parse_path(path)
    assert msg_part in str(exc_info.value)
