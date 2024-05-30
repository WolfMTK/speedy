from speedy.datastructures.url import URL


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


def test_url_eq() -> None:
    assert URL('') == URL('')
    assert URL('/foo') == '/foo'
    assert URL('') != 1


def test_url_repr() -> None:
    url = URL('https://example.org:8000/path/to/somewhere?abc=123#anchor')
    assert repr(url) == "URL('https://example.org:8000/path/to/somewhere?abc=123#anchor')"


def test_url_replace_query() -> None:
    url = URL('https://example.org:8000/path/to/somewhere?abc=123#anchor')
    assert url.query == "abc=123"
    url = url.replace_query(order='name')
    assert str(url) == 'https://example.org:8000/path/to/somewhere?order=name#anchor'
    assert url.query == 'order=name'
    url = URL('https://example.org/path/to?a=1&b=2')
    assert url.query == 'a=1&b=2'


def test_url_include_query_params() -> None:
    url = URL('https://example.org/path/to?a=1')
    assert url.query == 'a=1'
    url = url.include_query_params(a=2)
    assert url.query == 'a=2'
    assert str(url) == 'https://example.org/path/to?a=2'
    url = url.include_query_params(search='test')
    assert url.query == 'a=2&search=test'
    assert str(url) == 'https://example.org/path/to?a=2&search=test'
