import functools
from enum import Enum

import pytest

from speedy.utils import url_quote
from speedy.utils.helpers import get_enum_string_value, unwrap_partial


def test_unwrap_partial() -> None:
    def func(*args: int) -> int:
        return sum(args)

    wrapped = functools.partial(functools.partial(functools.partial(func, 1), 2))

    assert wrapped() == 3
    assert unwrap_partial(wrapped) is func


def test_get_enum_string_value() -> None:
    data = "foo"
    assert get_enum_string_value(data) == "foo"
    data = Enum("Foo", {"name": "foo"})
    assert get_enum_string_value(data.name) == "foo"


def test_url_quote_preserves_safe_chars() -> None:
    safe_string = "/#%[]=:;$&()+,!?*@'~"
    assert url_quote(safe_string) == safe_string


def test_url_quote_encodes_spaces() -> None:
    assert url_quote("hello world") == "hello%20world"


@pytest.mark.parametrize(
    "char, encoded",
    [
        ('"', "%22"),
        ("<", "%3C"),
        (">", "%3E"),
        ("{", "%7B"),
        ("}", "%7D"),
        ("|", "%7C"),
        ("\\", "%5C"),
        ("^", "%5E"),
        ("`", "%60"),
    ],
)
def test_url_quote_encodes_unsafe_chars(char: str, encoded: str) -> None:
    assert url_quote(char) == encoded


def test_url_quote_handles_bytes() -> None:
    assert url_quote(b"test/path") == "test/path"
    assert url_quote(b"test file") == "test%20file"


def test_url_quote_alphanumeric() -> None:
    assert url_quote("abc123") == "abc123"


def test_url_quote_complex_scenario() -> None:
    original = "users/:id/file name"
    expected = "users/:id/file%20name"
    assert url_quote(original) == expected
