from typing import Mapping, Any

import pytest

from speedy._layers.utils import narrow_response_cookies, narrow_response_headers
from speedy.datastructures import Cookie, ResponseHeader


class CustomDict(Mapping):
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
        (None, ()),
        ({}, ()),
        ([], ()),
        ((), ()),
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
    assert isinstance(result, tuple)
    assert result == expected_output
    if isinstance(input_cookies, list):
        assert result is not input_cookies


@pytest.mark.parametrize(
    "input_headers, expected_output",
    [
        (None, ()),
        ({}, ()),
        ([], ()),
        ((), ()),
        (
                {"Content-Type": "application/json"},
                (ResponseHeader(name="Content-Type", value="application/json"),),
        ),
        (
                {"X-Request-ID": "123", "Cache-Control": "no-cache"},
                (
                        ResponseHeader(name="X-Request-ID", value="123"),
                        ResponseHeader(name="Cache-Control", value="no-cache"),
                ),
        ),
        (
                CustomDict({"Server": "Speedy/1.0"}),
                (ResponseHeader(name="Server", value="Speedy/1.0"),),
        ),
        (
                [ResponseHeader(name="Set-Cookie", value="session=abc")],
                (ResponseHeader(name="Set-Cookie", value="session=abc"),),
        ),
        (
                (
                        ResponseHeader(name="ETag", value="xyz"),
                        ResponseHeader(name="Vary", value="Accept-Encoding"),
                ),
                (
                        ResponseHeader(name="ETag", value="xyz"),
                        ResponseHeader(name="Vary", value="Accept-Encoding"),
                ),
        ),
    ],
)
def test_narrow_response_headers(input_headers: Any, expected_output: tuple[ResponseHeader, ...]) -> None:
    result = narrow_response_headers(input_headers)
    assert isinstance(result, tuple)
    assert result == expected_output
    if isinstance(input_headers, list):
        assert result is not input_headers
