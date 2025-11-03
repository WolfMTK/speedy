from typing import Mapping, Any

import pytest

from speedy._layers.utils import narrow_response_cookies
from speedy.datastructures import Cookie


class CustomDict(Mapping):
    """A minimal custom mapping for testing."""
    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)


@pytest.mark.parametrize(
    "input_cookies, expected_output",
    [
        # None → empty tuple
        (None, ()),

        # Empty containers → empty tuple
        ({}, ()),
        ([], ()),
        ((), ()),

        # Mapping with values → tuple of Cookies
        (
            {"sessionid": "abc123"},
            (Cookie(key="sessionid", value="abc123"),),
        ),
        (
            {"a": "1", "b": "2"},
            (Cookie(key="a", value="1"), Cookie(key="b", value="2")),
        ),
        (
            CustomDict({"lang": "en"}),
            (Cookie(key="lang", value="en"),),
        ),

        # Sequence of Cookies → same Cookies in tuple
        (
            [Cookie(key="x", value="10")],
            (Cookie(key="x", value="10"),),
        ),
        (
            (Cookie(key="p", value="1"), Cookie(key="q", value="2")),
            (Cookie(key="p", value="1"), Cookie(key="q", value="2")),
        ),
    ],
)
def test_narrow_response_cookies(input_cookies: Any, expected_output: tuple[Cookie, ...]) -> None:
    result = narrow_response_cookies(input_cookies)

    # Always returns a tuple
    assert isinstance(result, tuple)

    # Content matches expected
    assert result == expected_output

    # Ensure immutability: never returns original list
    if isinstance(input_cookies, list):
        assert result is not input_cookies
