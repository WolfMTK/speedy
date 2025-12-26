from typing import Any

import pytest

from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.routes.helpers import param_type_map, _validate_path_parameter


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
