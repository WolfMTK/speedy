import pytest

from speedy.datastructures.url import URL, URLComponents, URLPath, QueryParams


@pytest.mark.parametrize(
    'base, path', [
        ('http://example.org', 'foo/bar?a=1&b=2'),
        ('http://example.org/', 'foo/bar?a=1&b=2'),
        ('http://example.org', '/foo/bar?a=1&b=2'),
        ('http://example.org', '/foo/bar?a=1&b=2')
    ]
)
def test_url_path(base: str, path: str) -> None:
    result = 'http://example.org/foo/bar?a=1&b=2'
    assert str(URLPath(path, base)) == result


@pytest.mark.parametrize(
    'base, path', [
        ('http://example.org', 'foo/bar?a=1&b=2'),
        ('http://example.org/', 'foo/bar?a=1&b=2'),
        ('http://example.org', '/foo/bar?a=1&b=2'),
        ('http://example.org', '/foo/bar?a=1&b=2')
    ]
)
def test_url_path_repr(base: str, path: str) -> None:
    assert repr(URLPath(path, base)) == f"URLPath(path={path!r}, base={base!r})"


def test_url() -> None:
    url = URL('https://example.org:8000/path/to/somewhere?abc=123#anchor')
    assert url.scheme == 'https'
    assert url.hostname == 'example.org'
    assert url.port == 8000
    assert url.netloc == 'example.org:8000'
    assert url.username is None
    assert url.password is None
    assert url.path == '/path/to/somewhere'
    assert url.query == 'abc=123'
    assert url.fragment == "anchor"


@pytest.mark.parametrize(
    'component, value', [
        ('scheme', 'https'),
        ('netloc', 'example.org'),
        ('path', '/foo/to'),
        ('query', 'a=1'),
        ('fragment', 'anchor')
    ]
)
def test_from_components(component: str, value: str) -> None:
    url_component = URLComponents(**{component: value})
    expected = {'scheme': '', 'netloc': '', 'path': '', 'query': '', 'fragment': '', component: value}
    url = URL.from_components(url_component)
    for key, value in expected.items():
        assert getattr(url, key) == value


def test_replace() -> None:
    url = URL('https://example.org:8000/path/to/somewhere?abc=123#anchor')
    new_url = url.replace(scheme='http')
    assert new_url == 'http://example.org:8000/path/to/somewhere?abc=123#anchor'
    assert new_url.scheme == 'http'

    new_url = url.replace(port=None)
    assert new_url == 'https://example.org/path/to/somewhere?abc=123#anchor'
    assert new_url.port is None

    new_url = url.replace(hostname='example.com')
    assert new_url == 'https://example.com:8000/path/to/somewhere?abc=123#anchor'
    assert new_url.hostname == 'example.com'

    ipv6_url = URL('https://[fe::2]:12345')
    new_ipv6_url = ipv6_url.replace(port=8000)
    assert new_ipv6_url == 'https://[fe::2]:8000'
    assert new_ipv6_url.port == 8000

    new_ipv6_url = ipv6_url.replace(username='username', password='password')
    assert new_ipv6_url == 'https://username:password@[fe::2]:12345'
    assert new_ipv6_url.netloc == 'username:password@[fe::2]:12345'
    assert new_ipv6_url.username == 'username'
    assert new_ipv6_url.password == 'password'

    ipv6_url = URL('https://[fe::2]')
    new_ipv6_url = ipv6_url.replace(port=8000)
    assert new_ipv6_url == 'https://[fe::2]:8000'
    assert new_ipv6_url.port == 8000

    url = URL('http://u:p@host/')
    new_url = url.replace(hostname='foo')
    assert new_url == 'http://u:p@foo/'
    assert new_url.hostname == 'foo'

    url = URL('http://host:80')
    new_url = url.replace(username='user')
    assert new_url == 'http://user@host:80'


def test_url_eq() -> None:
    assert URL('') == URL('')
    assert URL('/foo') == '/foo'
    assert URL('') != 1


def test_url_repr() -> None:
    url = URL('https://example.org:8000/path/to/somewhere?abc=123#anchor')
    assert repr(url) == "URL('https://example.org:8000/path/to/somewhere?abc=123#anchor')"


def test_url_replace_query_params() -> None:
    url = URL('https://example.org:8000/path/to/somewhere?abc=123#anchor')
    assert url.query == 'abc=123'
    url = url.replace_query_params(order='name')
    assert url == 'https://example.org:8000/path/to/somewhere?order=name#anchor'
    assert url.query == 'order=name'


def test_url_remove_query_params() -> None:
    url = URL('https://example.org/path/to?a=1&b=2')
    assert url.query == 'a=1&b=2'
    url = url.remove_query_params('a')
    assert url == 'https://example.org/path/to?b=2'
    assert url.query == 'b=2'
    url = URL('https://example.org/path/to?a=1&b=2&c=3')
    url = url.remove_query_params(('a', 'b', 'c'))
    assert url == 'https://example.org/path/to'
    assert url.query == ''


def test_url_include_query_params() -> None:
    url = URL('https://example.org/path/to?a=1')
    assert url.query == 'a=1'
    url = url.include_query_params(a=2)
    assert url.query == 'a=2'
    assert url == 'https://example.org/path/to?a=2'
    url = url.include_query_params(search='test')
    assert url.query == 'a=2&search=test'
    assert url == 'https://example.org/path/to?a=2&search=test'


def test_hidden_password() -> None:
    url = URL('https://example.org/path/to?a=1')
    assert repr(url) == "URL('https://example.org/path/to?a=1')"
    url = URL('https://username@example.org/path/to?a=1')
    assert repr(url) == "URL('https://username@example.org/path/to?a=1')"
    url = URL('https://username:password@example.org/path/to?a=1')
    assert repr(url) == "URL('https://username:**********@example.org/path/to?a=1')"


def test_url_from_scope() -> None:
    url = URL.from_scope(
        {
            'path': '/path/to/somewhere',
            'query_string': b'a=1',
            'headers': []
        }
    )
    assert url == '/path/to/somewhere?a=1'
    assert repr(url) == "URL('/path/to/somewhere?a=1')"

    url = URL.from_scope(
        {
            'scheme': 'https',
            'server': ('example.org', 8000),
            'path': '/path/to/somewhere',
            'query_string': b'a=1',
            'headers': []
        }
    )
    assert url == 'https://example.org:8000/path/to/somewhere?a=1'
    assert repr(url) == "URL('https://example.org:8000/path/to/somewhere?a=1')"

    url = URL.from_scope({
        'scheme': 'http',
        'path': '/path/to/somewhere',
        'query_string': b'a=1',
        'headers': [
            (b'content-type', b'text/html'),
            (b'host', b'example.com:8000'),
            (b'accept', b'text/html')
        ]
    })

    assert url == 'http://example.com:8000/path/to/somewhere?a=1'
    assert repr(url) == "URL('http://example.com:8000/path/to/somewhere?a=1')"

    url = URL.from_scope({
        'scheme': 'https',
        'server': ('example.org', 443),
        'path': '/path/to/somewhere',
        'query_string': b'a=1',
        'headers': []
    })
    assert url == 'https://example.org/path/to/somewhere?a=1'
    assert repr(url) == "URL('https://example.org/path/to/somewhere?a=1')"


def test_query_params() -> None:
    query = QueryParams('a=123&a=456&b=789')
    assert 'a' in query
    assert 'A' not in query
    assert 'c' not in query
    assert query['a'] == '456'
    assert query.get('nope') is None
    assert sorted(query.getList('a')) == sorted(['123', '456'])
    assert sorted(query.items()) == sorted([('a', '456'), ('b', '789')])
    assert repr(query) == "QueryParams('a=123&a=456&b=789')"


def test_query_params_repr() -> None:
    query = QueryParams('a=123&b=456')
    assert repr(query) == "QueryParams('a=123&b=456')"
    query = QueryParams({'a': '123', 'b': '456'})
    assert repr(query) == "QueryParams('a=123&b=456')"
    query = QueryParams([('a', 123), ('b', 456)])
    assert repr(query) == "QueryParams('a=123&b=456')"


def test_query_params_eq() -> None:
    assert QueryParams({'a': '123', 'b': '456'}) == QueryParams([('a', '123'), ('b', '456')])
    assert QueryParams({'a': '123', 'b': '456'}) == QueryParams({'a': '123', 'b': '456'})
    assert QueryParams({'a': '123', 'b': '456'}) == QueryParams('a=123&b=456')
    assert QueryParams({'a': '123', 'b': '456'}) == QueryParams({'b': '456', 'a': '123'})
    assert QueryParams() == QueryParams([])
    assert QueryParams([('a', '123'), ('a', '456')]) == QueryParams('a=123&a=456')
    assert QueryParams({'a': '123', 'b': '456'}) != 'null'
    query = QueryParams([('a', '123'), ('b', '456')])
    assert QueryParams(query) == query


def test_url_blank_params() -> None:
    query = QueryParams('a=123&abc&def&b=456')
    assert 'a' in query
    assert 'abc' in query
    assert 'def' in query
    assert 'b' in query
    value = query.get('abc')
    assert value is not None
    assert len(value) == 0
    assert len(query['a']) == 3
    assert sorted(query.keys()) == sorted(['a', 'abc', 'def', 'b'])
