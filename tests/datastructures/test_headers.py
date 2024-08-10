import pytest

from speedy.datastructures import Headers, MutableHeaders


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


def test_headers_repr() -> None:
    headers = Headers({'a': '123', 'b': '789'})
    assert repr(headers) == "Headers({'a': '123', 'b': '789'})"
    headers = Headers(raw=[(b'a', b'123'), (b'a', b'456'), (b'b', b'789')])
    assert repr(headers) == "Headers(raw=[(b'a', b'123'), (b'a', b'456'), (b'b', b'789')])"


def test_headers_raw() -> None:
    headers = Headers({'a': '123', 'b': '789'})
    assert headers['a'] == '123'
    assert headers['A'] == '123'
    assert headers['b'] == '789'
    assert headers.raw == [(b'a', b'123'), (b'b', b'789')]


def test_headers_mutablecopy() -> None:
    headers = Headers(raw=[(b'a', b'123'), (b'a', b'456'), (b'b', b'789')])
    headers_copy = headers.mutablecopy()
    assert headers_copy.items() == [('a', '123'), ('a', '456'), ('b', '789')]
    headers_copy['a'] = '346'
    assert headers_copy.items() == [('a', '346'), ('b', '789')]
    assert headers_copy != headers


def test_headers_from_scope() -> None:
    headers = Headers(scope={'headers': ((b'a', b'1'),)})
    assert dict(headers) == {'a': '1'}
    assert list(headers.items()) == [('a', '1')]
    assert list(headers.raw) == [(b'a', b'1')]


def test_mutable_headers() -> None:
    headers = MutableHeaders()
    assert dict(headers) == {}
    headers['a'] = '1'
    assert dict(headers) == {'a': '1'}
    headers['a'] = '2'
    assert dict(headers) == {'a': '2'}
    headers.setdefault('a', '3')
    assert dict(headers) == {'a': '2'}
    headers.setdefault('b', '4')
    assert dict(headers) == {'a': '2', 'b': '4'}
    del headers['a']
    assert dict(headers) == {'b': '4'}
    assert headers.raw == [(b'b', b'4')]


@pytest.mark.parametrize(
    'value', (MutableHeaders({'a': '1'}),
              {'a': '1'})
)
def test_mutable_headers_merge(value: MutableHeaders | dict[str, str]) -> None:
    headers = MutableHeaders()
    headers = headers | value
    assert isinstance(headers, MutableHeaders)
    assert dict(headers) == {'a': '1'}
    assert headers.items() == [('a', '1',)]
    assert headers.raw == [(b'a', b'1')]


@pytest.mark.parametrize(
    'value', (MutableHeaders({'a': '1'}),
              {'a': '1'})
)
def test_mutable_headers_update(value: MutableHeaders | dict[str, str]) -> None:
    headers = MutableHeaders()
    headers |= value
    assert isinstance(headers, MutableHeaders)
    assert dict(headers) == {'a': '1'}
    assert headers.items() == [('a', '1',)]
    assert headers.raw == [(b'a', b'1',)]


def test_mutable_headers_merge_not_mapping() -> None:
    headers = MutableHeaders()
    with pytest.raises(TypeError):
        headers |= {'error'}  # type: ignore
    with pytest.raises(TypeError):
        headers | {'error'}  # type: ignore


def test_mutable_headers_from_scope() -> None:
    headers = MutableHeaders(scope={'headers': ((b'a', b'1'),)})
    assert dict(headers) == {'a': '1'}
    headers.update({'b': '2'})
    assert dict(headers) == {'a': '1', 'b': '2'}
    assert list(headers.items()) == [('a', '1'), ('b', '2',)]
    assert list(headers.raw) == [(b'a', b'1'), (b'b', b'2')]
