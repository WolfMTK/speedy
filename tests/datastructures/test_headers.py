from speedy.datastructures import Headers


def test_headers() -> None:
    headers = Headers(raw=[(b'a', b'123'), (b'a', b'456'), (b'b', b'789')])
    assert 'a' in headers
    assert 'A' in headers
    assert 'b' in headers
    assert 'B' in headers
    assert 'c' not in headers


def test_headers_to_mapper() -> None:
    headers = Headers(raw=[(b'a', b'123'), (b'a', b'456'), (b'b', b'789')])
    assert headers['a'] == '123'
    assert headers.get('a') == '123'
    assert headers.get('null') is None
    assert headers.getlist('a') == sorted(['123', '456'])
    assert headers.keys() == ['a', 'a', 'b']
    assert headers.values() == ['123', '456', '789']
    assert headers.items() == [('a', '123'), ('a', '456'), ('b', '789')]
    assert list(headers) == ['a', 'a', 'b']
    assert dict(headers) == {'a': '123', 'b': '789'}


def test_headers_eq() -> None:
    headers = Headers(raw=[(b'a', b'123'), (b'a', b'456'), (b'b', b'789')])
    assert headers == Headers(raw=[(b'a', b'123'), (b'a', b'456'), (b'b', b'789')])
    assert headers != [(b'a', b'123'), (b'a', b'456'), (b'b', b'789')]
    assert headers != Headers(raw=[(b'a', b'123'), (b'a', b'456'), (b'b', b'789'), (b'c', b'455')])


def test_headers_raw() -> None:
    headers = Headers({'a': '123', 'b': '789'})
    assert headers['a'] == '123'
    assert headers['A'] == '123'
    assert headers['b'] == '789'
    assert headers.raw == [(b'a', b'123'), (b'b', b'789')]
