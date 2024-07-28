from speedy.datastructures import ImmutableMultiDict

ZERO = 0


def test_immutable_multi_dict_getList() -> None:
    multi_dict = ImmutableMultiDict([('a', '123'), ('a', '456'), ('b', '789')], c='12')
    assert isinstance(multi_dict.getList('a'), list)
    assert multi_dict.getList('a') == ['123', '456']
    assert multi_dict.getList('b') == ['789']
    assert multi_dict.getList('c') == ['12']


def test_immutable_multi_dict_multi_items() -> None:
    multi_dict = ImmutableMultiDict([('a', '123'), ('a', '456'), ('b', '789')], c='12')
    items = multi_dict.multi_items()
    assert isinstance(items, list)
    assert len(items) > 1
    assert sorted(items) == sorted([('a', '123'), ('a', '456'), ('b', '789'), ('c', '12')])


def test_immutable_multi_dict() -> None:
    multi_dict = ImmutableMultiDict([('a', '123'), ('a', '456'), ('b', '789')], c='12')
    keys = ('a', 'b', 'c')
    values = ('456', '789', '12')
    assert sorted(multi_dict.keys()) == sorted(keys)
    assert sorted(multi_dict.values()) == sorted(values)

    for key, value in multi_dict.items():
        assert key in keys
        assert value in values

    for key in multi_dict:
        assert key in keys

    assert multi_dict['a'] == '456'
    values = ['444', '565']
    multi_dict['b'] = values
    assert multi_dict['b'] == values[-1]
    assert sorted(multi_dict.getList('b')) == sorted(values)
    assert multi_dict.pop('b') == values[-1]
    assert len(multi_dict.getList('b')) == ZERO

    kwargs = {'d': ['544', '231']}
    for key, value in kwargs.items():
        multi_dict[key] = value
        assert multi_dict.popitem() == (key, value[-1])

    for key, value in kwargs.items():
        multi_dict[key] = value
        assert sorted(multi_dict.poplist(key)) == sorted(value)

    value = ('d', '300')
    multi_dict.update([value])
    assert multi_dict['d'] == value[-1]

    value = {'d': '450'}
    multi_dict.update(value)
    assert multi_dict['d'] == value['d']

    value = ImmutableMultiDict([('d', '200')])
    multi_dict.update(value)
    assert multi_dict['d'] == value['d']

    del multi_dict['c']
    assert multi_dict.get('c') is None

    multi_dict.append('c', '322')
    assert multi_dict['c'] == '322'

    multi_dict.clear()
    assert len(multi_dict.multi_items()) == ZERO
    assert len(multi_dict.items()) == ZERO
