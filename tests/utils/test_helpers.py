import functools
from enum import Enum

from speedy.utils.helpers import unwrap_partial, get_enum_string_value


def test_unwrap_partial() -> None:
    def func(*args: int) -> int:
        return sum(args)

    wrapped = functools.partial(functools.partial(functools.partial(func, 1), 2))

    assert wrapped() == 3
    assert unwrap_partial(wrapped) is func


def test_get_enum_string_value() -> None:
    data = "foo"
    assert get_enum_string_value(data) == "foo"
    data = Enum('Foo', {'name': 'foo'})
    assert get_enum_string_value(data.name) == "foo"
