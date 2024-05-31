import pytest

from speedy.datastructures.url import URL, URLComponents


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
    assert str(new_url) == 'http://example.org:8000/path/to/somewhere?abc=123#anchor'
    assert new_url.scheme == 'http'

    new_url = url.replace(port=None)
    assert str(new_url) == 'https://example.org/path/to/somewhere?abc=123#anchor'
    assert new_url.port is None

    new_url = url.replace(hostname='example.com')
    assert str(new_url) == 'https://example.com:8000/path/to/somewhere?abc=123#anchor'
    assert new_url.hostname == 'example.com'

    ipv6_url = URL('https://[fe::2]:12345')
    new_ipv6_url = ipv6_url.replace(port=8000)
    assert str(new_ipv6_url) == 'https://[fe::2]:8000'
    assert new_ipv6_url.port == 8000

    new_ipv6_url = ipv6_url.replace(username='username', password='password')
    assert str(new_ipv6_url) == 'https://username:password@[fe::2]:12345'
    assert new_ipv6_url.netloc == 'username:password@[fe::2]:12345'
    assert new_ipv6_url.username == 'username'
    assert new_ipv6_url.password == 'password'

    ipv6_url = URL('https://[fe::2]')
    new_ipv6_url = ipv6_url.replace(port=8000)
    assert str(new_ipv6_url) == 'https://[fe::2]:8000'
    assert new_ipv6_url.port == 8000

    url = URL('http://u:p@host/')
    new_url = url.replace(hostname='foo')
    assert str(new_url) == 'http://u:p@foo/'
    assert new_url.hostname == 'foo'

    url = URL('http://host:80')
    new_url = url.replace(username='user')
    assert str(new_url) == 'http://user@host:80'


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
    assert str(url) == 'https://example.org:8000/path/to/somewhere?order=name#anchor'
    assert url.query == 'order=name'


def test_url_remove_query_params() -> None:
    url = URL('https://example.org/path/to?a=1&b=2')
    assert url.query == 'a=1&b=2'
    url = url.remove_query_params('a')
    assert str(url) == 'https://example.org/path/to?b=2'
    assert url.query == 'b=2'
    url = URL('https://example.org/path/to?a=1&b=2&c=3')
    url = url.remove_query_params(('a', 'b', 'c'))
    assert str(url) == 'https://example.org/path/to'
    assert url.query == ''


def test_url_include_query_params() -> None:
    url = URL('https://example.org/path/to?a=1')
    assert url.query == 'a=1'
    url = url.include_query_params(a=2)
    assert url.query == 'a=2'
    assert str(url) == 'https://example.org/path/to?a=2'
    url = url.include_query_params(search='test')
    assert url.query == 'a=2&search=test'
    assert str(url) == 'https://example.org/path/to?a=2&search=test'


def test_hidden_password() -> None:
    url = URL('https://example.org/path/to?a=1')
    assert repr(url) == "URL('https://example.org/path/to?a=1')"
    url = URL('https://username@example.org/path/to?a=1')
    assert repr(url) == "URL('https://username@example.org/path/to?a=1')"
    url = URL('https://username:password@example.org/path/to?a=1')
    assert repr(url) == "URL('https://username:**********@example.org/path/to?a=1')"
