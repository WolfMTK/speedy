from typing import Any
from urllib.parse import urlencode

import pytest

from speedy._parsers import parse_query_string, parse_cookie_string
from speedy.datastructures import Cookie


def _parse_query_string(query: dict[str, Any], query_string: bytes | str) -> None:
    query_string = parse_query_string(query_string)
    for key, value in query.items():
        if isinstance(value, list) and len(value) > 1:
            for i in value:
                assert (key, str(i)) in query_string
        else:
            assert (key, str(value)) in query_string


def test_parse_query_string() -> None:
    query = {
        'value': 10,
        'rating': '10',
        'is_active': True,
        'animal': ['cat', 'wolf']
    }
    query_string = urlencode(query, doseq=True).encode()
    _parse_query_string(query, query_string)
    query_string = urlencode(query, doseq=True)
    _parse_query_string(query, query_string)


@pytest.mark.parametrize(
    'cookie_string, expected',
    (
            ('ABC    = 123;   efg  =   456', {'ABC': '123', 'efg': '456'}),
            ('foo= ; bar=', {'foo': '', 'bar': ''}),
            ('foo="bar=123456789&name=moisheZuchmir"', {'foo': 'bar=123456789&name=moisheZuchmir'}),
            ('email=%20%22%2c%3b%2f', {'email': ' ",;/'}),
            ('foo=%1;bar=bar', {'foo': '%1', 'bar': 'bar'}),
            ('foo=bar;fizz  ; buzz', {'': 'buzz', 'foo': 'bar'}),
            ('  fizz; foo=  bar', {'': 'fizz', 'foo': 'bar'}),
            ('foo=false;bar=bar;foo=true', {'bar': 'bar', 'foo': 'true'}),
            ('foo=;bar=bar;foo=boo', {'bar': 'bar', 'foo': 'boo'}),
            (
                    Cookie(key='abc', value='123', path='/head', domain='localhost').to_header(header=''),
                    {'Domain': 'localhost', 'Path': '/head', 'SameSite': 'lax', 'abc': '123'},
            ),
    ),
)
def test_parse_cookie_string(cookie_string: str, expected: dict[str, str]) -> None:
    assert parse_cookie_string(cookie_string) == expected
