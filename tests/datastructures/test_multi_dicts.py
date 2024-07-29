from speedy.datastructures import ImmutableMultiDict, MultiDict

ZERO = 0


def test_immutable_multidict_getList() -> None:
    multidict = ImmutableMultiDict([('a', '123'), ('a', '456'), ('b', '789')], c='12')
    assert isinstance(multidict.getList('a'), list)
    assert multidict.getList('a') == ['123', '456']
    assert multidict.getList('b') == ['789']
    assert multidict.getList('c') == ['12']


def test_immutable_multidict_multi_items() -> None:
    multidict = ImmutableMultiDict([('a', '123'), ('a', '456'), ('b', '789')], c='12')
    items = multidict.multi_items()
    assert isinstance(items, list)
    assert len(items) > 1
    assert sorted(items) == sorted([('a', '123'), ('a', '456'), ('b', '789'), ('c', '12')])


def test_immutable_multidict() -> None:
    multidict = ImmutableMultiDict([('a', '123'), ('a', '456'), ('b', '789')], c='12')
    keys = ('a', 'b', 'c')
    values = ('456', '789', '12')
    assert sorted(multidict.keys()) == sorted(keys)
    assert sorted(multidict.values()) == sorted(values)

    for key, value in multidict.items():
        assert key in keys
        assert value in values

    for key in multidict:
        assert key in keys

    assert multidict['a'] == '456'
    values = ['444', '565']
    multidict['b'] = values
    assert multidict['b'] == values[-1]
    assert sorted(multidict.getList('b')) == sorted(values)
    assert multidict.pop('b') == values[-1]
    assert len(multidict.getList('b')) == ZERO

    kwargs = {'d': ['544', '231']}
    for key, value in kwargs.items():
        multidict[key] = value
        assert multidict.popitem() == (key, value[-1])

    for key, value in kwargs.items():
        multidict[key] = value
        assert sorted(multidict.poplist(key)) == sorted(value)

    value = ('d', '300')
    multidict.update([value])
    assert multidict['d'] == value[-1]

    value = {'d': '450'}
    multidict.update(value)
    assert multidict['d'] == value['d']

    value = ImmutableMultiDict([('d', '200')])
    multidict.update(value)
    assert multidict['d'] == value['d']

    del multidict['c']
    assert multidict.get('c') is None

    multidict.append('c', '322')
    assert multidict['c'] == '322'

    multidict.clear()
    assert len(multidict.multi_items()) == ZERO
    assert len(multidict.items()) == ZERO


def test_multidict():
    multidict = MultiDict([('a', '123'), ('a', '456'), ('b', '789')], c='12')

    assert 'a' in multidict
    assert 'A' not in multidict
    assert 'c' in multidict
    assert multidict['a'] == '456'
    assert multidict.get('a') == '456'
    assert multidict.get('d') is None
    assert multidict.getList('a') == ['123', '456']
    assert list(multidict.keys()) == ['a', 'b', 'c']
    assert list(multidict.values()) == ['456', '789', '12']
    assert list(multidict.items()) == [('a', '456'), ('b', '789'), ('c', '12',)]
    assert len(multidict) == 3
    assert list(multidict) == ['a', 'b', 'c']
    assert dict(multidict) == {'a': '456', 'b': '789', 'c': '12'}
    assert str(multidict) == "MultiDict([('a', '123'), ('a', '456'), ('b', '789'), ('c', '12')])"
    assert repr(multidict) == "MultiDict([('a', '123'), ('a', '456'), ('b', '789'), ('c', '12')])"
    assert MultiDict({'a': '123', 'b': '456'}) == MultiDict([('a', '123'), ('b', '456')])
    assert MultiDict({'a': '123', 'b': '456'}) == MultiDict({'a': '123', 'b': '456'})
    assert MultiDict() == MultiDict({})
    assert MultiDict({'a': '123', 'b': '456'}) != 'invalid'


def test_multidict_update():
    multidict = MultiDict([('a', '123'), ('b', '456',)])
    multidict.update({'a': '789'})
    assert multidict.getList('a') == ['789']
    assert multidict == MultiDict([('a', '789'), ('b', '456')])

    multidict = MultiDict([('a', '123'), ('b', '456',)])
    multidict.update(multidict)
    assert repr(multidict) == "MultiDict([('a', '123'), ('b', '456')])"

    multidict = MultiDict([('a', '123'), ('a', '456',)])
    multidict.update([('a', '123',)])
    assert multidict.getList('a') == ['123']
    multidict.update([('a', '456')], a='789', b='123')
    assert multidict == MultiDict([('a', '456'), ('a', '789'), ('b', '123')])


def test_multidict_append():
    multidict = MultiDict([('a', '123')])
    multidict.append('a', '456')
    assert multidict.getList('a') == ['123', '456']
    assert repr(multidict) == "MultiDict([('a', '123'), ('a', '456')])"


def test_multidict_setdefault():
    multidict = MultiDict([('a', '123')])
    assert multidict.setdefault('a', '456') == '123'
    assert multidict.getList('a') == ['123']
    assert multidict.setdefault('b', '456') == '456'
    assert multidict.getList('b') == ['456']
    assert repr(multidict) == "MultiDict([('a', '123'), ('b', '456')])"


def test_multidict_setlist():
    multidict = MultiDict([('a', '123')])
    multidict.setlist('a', ['456', '789'])
    assert multidict.getList('a') == ['456', '789']
    multidict.setlist('b', [])
    assert 'b' not in multidict


def test_multidict_clear():
    multidict = MultiDict([('a', '123'), ('a', '456'), ('b', '789')])
    multidict.clear()
    assert multidict.get('a') is None
    assert repr(multidict) == 'MultiDict([])'


def test_multidict_poplist():
    multidict = MultiDict([('a', '123'), ('a', '456'), ('b', '789')])
    assert multidict.poplist('a') == ['123', '456']
    assert multidict.get('a') is None
    assert repr(multidict) == "MultiDict([('b', '789')])"


def test_multidict_popitem():
    multidict = MultiDict([('a', '123'), ('a', '456'), ('b', '789')])
    item = multidict.popitem()
    assert multidict.get(item[0]) is None


def test_multidict_pop():
    multidict = MultiDict([('a', '123'), ('a', '456'), ('b', '789')])
    assert multidict.pop('a') == '456'
    assert multidict.get('a') is None
    assert repr(multidict) == "MultiDict([('b', '789')])"


def test_multidict_del():
    multidict = MultiDict([('a', '123'), ('a', '456',)])
    del multidict['a']
    assert multidict.get('a') is None
    assert repr(multidict) == 'MultiDict([])'


def test_multidict_get():
    multidict = MultiDict([('a', '123'), ('a', '456',)])
    multidict['a'] = '789'
    assert multidict['a'] == '789'
    assert multidict.get('a') == '789'
    assert multidict.getList('a') == ['789']


def test_multidict_eq():
    multidict = MultiDict([('a', '123'), ('a', '456',)])
    assert MultiDict(multidict) == multidict
