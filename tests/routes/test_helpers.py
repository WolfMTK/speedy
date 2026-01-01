import datetime
from typing import Any

import pytest

from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.routes.helpers import (
    param_type_map,
    _validate_path_parameter,
    _parse_datetime,
    _parse_date,
    _parse_time,
    _parse_timedelta,
)


@pytest.mark.parametrize("key_type", param_type_map.keys())
def test_valid_types(key_type: Any) -> None:
    param_name = "param"
    param = f"{param_name}:{key_type}"
    path = f"/api/{{{param}}}"
    print(path)
    _validate_path_parameter(param, path)


def test_valid_parameter_with_whitespace() -> None:
    _validate_path_parameter(" id : int", "/path/{id}")
    _validate_path_parameter("user_id:uuid ", "/users/{user_id}")


def test_valid_complex_types() -> None:
    _validate_path_parameter("start:date", "/events/{start}")
    _validate_path_parameter("created_at:datetime", "/logs/{created_at}")
    _validate_path_parameter("file_path:path", "/files/{file_path}")


def test_no_separator_raises_exception() -> None:
    path = "/users/id"
    param = "id_int"

    with pytest.raises(ImproperlyConfiguredException) as exc_info:
        _validate_path_parameter(param, path)

    assert "declared with a type" in str(exc_info.value)
    assert path in str(exc_info.value)


def test_empty_name_raises_exception() -> None:
    path = "/users/{:int}"
    param = ":int"

    with pytest.raises(ImproperlyConfiguredException) as exc_info:
        _validate_path_parameter(param, path)

    assert "length greater than zero" in str(exc_info.value)


def test_empty_type_raises_exception() -> None:
    path = "/users/{id:}"
    param = "id:"

    with pytest.raises(ImproperlyConfiguredException) as exc_info:
        _validate_path_parameter(param, path)

    assert "allowed type" in str(exc_info.value)
    assert "int" in str(exc_info.value)


def test_invalid_type_raises_exception() -> None:
    path = "/items/{item:wrongtype}"
    param = "item:wrongtype"

    with pytest.raises(ImproperlyConfiguredException) as exc_info:
        _validate_path_parameter(param, path)

    assert "allowed type" in str(exc_info.value)
    assert "wrongtype" in str(exc_info.value)
    assert path in str(exc_info.value)


def test_multiple_separators_behavior() -> None:
    param = "id:int:extra"
    path = "/path/{id:int:extra}"

    with pytest.raises(ImproperlyConfiguredException) as exc_info:
        _validate_path_parameter(param, path)

    assert "allowed type" in str(exc_info.value)


def test_only_whitespace_name_raises_exception() -> None:
    param = "   :int"
    path = "/path/{:int}"

    with pytest.raises(ImproperlyConfiguredException) as exc_info:
        _validate_path_parameter(param, path)

    assert "length greater than zero" in str(exc_info.value)


@pytest.mark.parametrize(
    "value, expected", [
        ("1972-10-03T14:30:00", datetime.datetime(1972, 10, 3, 14, 30, 0)),
        ("1972-10-03T14:30:00.123456", datetime.datetime(
            1972, 10, 3, 14, 30, 0, 123456,
        )),
        ("1972-10-03T14:30:00+03:00", datetime.datetime(
            1972, 10, 3, 14, 30, 0,
            tzinfo=datetime.timezone(datetime.timedelta(hours=3)),
        )),
    ],
)
def test_parse_datetime_valid_formats(
        value: str,
        expected: datetime.datetime,
) -> None:
    assert _parse_datetime(value) == expected


@pytest.mark.parametrize(
    "value, exp_microseconds", [
        ("1972-10-03T14:30:00Z", 0),
        ("1972-10-03T14:30:00.123Z", 123000),
    ],
)
def test_parse_datetime_z_suffix_conversion(
        value: str,
        exp_microseconds: int,
) -> None:
    result = _parse_datetime(value)
    assert result.tzinfo is not None
    assert result.utcoffset().total_seconds() == 0
    assert result.microsecond == exp_microseconds


def test_parse_datetime_invalid_format() -> None:
    with pytest.raises(ValueError):
        _parse_datetime("not-a-date")


def test_parse_date_valid() -> None:
    result = _parse_date("1972-10-03")
    expected = datetime.date(1972, 10, 3)
    assert result == expected


@pytest.mark.parametrize(
    "value", [
        "1972/10/03",
        "1972-03-40",
    ],
)
def test_parse_date_invalid_format(value: str) -> None:
    with pytest.raises(ValueError):
        _parse_date(value)


@pytest.mark.parametrize(
    "value, expected", [
        ("15:45:30", datetime.time(15, 45, 30)),
        ("15:45:30.123456", datetime.time(15, 45, 30, 123456)),
    ],
)
def test_parse_time_valid(value: str, expected: datetime.time) -> None:
    assert _parse_time(value) == expected


def test_parse_time_invalid_format() -> None:
    with pytest.raises(ValueError):
        _parse_time("25:00:00")


@pytest.mark.parametrize(
    "value, expected_delta", [
        ("10", datetime.timedelta(seconds=10)),
        ("10.5", datetime.timedelta(seconds=10.5)),
        ("-10", datetime.timedelta(seconds=-10)),
    ],
)
def test_parse_timedelta_from_numeric_string(
        value: str,
        expected_delta: datetime.timedelta,
) -> None:
    assert _parse_timedelta(value) == expected_delta
    assert _parse_timedelta(value).total_seconds() == expected_delta.total_seconds()


@pytest.mark.parametrize(
    "value, expected_delta", [
        ("01:00:00", datetime.timedelta(hours=1)),
        ("01:02:03", datetime.timedelta(hours=1, minutes=2, seconds=3)),
        ("00:00:01.500", datetime.timedelta(seconds=1, microseconds=500000)),
    ],
)
def test_parse_timedelta_from_time_format(
        value: str,
        expected_delta: datetime.timedelta,
) -> None:
    assert _parse_timedelta(value) == expected_delta


@pytest.mark.parametrize(
    "value", [
        "invalid_string",
        "PT1M",
    ],
)
def test_parse_timedelta_invalid_formats(value: str) -> None:
    with pytest.raises(ValueError) as exc_info:
        _parse_timedelta(value)

    assert "Invalid timedelta format" in str(exc_info.value)
