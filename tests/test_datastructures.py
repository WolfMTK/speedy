import operator
import sys
from copy import copy, deepcopy
from typing import Any, Iterator, Mapping

from pytest_mock import MockFixture

import pytest
from speedy.datastructures import (
    URL,
    Address,
    ImmutableState,
    State,
    URLPath,
    Headers,
    MutableHeaders,
    ImmutableMultiDict,
    MultiDict,
    QueryParams,
    UploadFile,
    FormMultiDict,
)
from speedy.exceptions import StateException

ZERO = 0


class _CustomMapping(Mapping):
    def __init__(self, value: dict[str, Any]) -> None:
        self._value = value

    def __getitem__(self, key: str) -> Any:
        return self._value[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._value)

    def __len__(self) -> int:
        return len(self._value)


class TestImmutableState:
    @pytest.mark.parametrize(
        "input_data, expected_dict",
        [
            ({"a": 1, "b": 2}, {"a": 1, "b": 2}),
            ({}, {}),
            (_CustomMapping({"a": 1}), {"a": 1}),
            ([("a", 1)], {"a": 1}),
            (ImmutableState({"a": 1}), {"a": 1}),
        ],
    )
    def test_init_types(self, input_data: Any, expected_dict: dict[str, Any]) -> None:
        assert dict(ImmutableState(input_data)) == expected_dict

    @pytest.mark.parametrize("invalid_value", [42, None])
    def test_init_invalid(self, invalid_value: Any) -> None:
        with pytest.raises(StateException, match="Invalid state type"):
            ImmutableState(invalid_value)

    def test_copy_data(self) -> None:
        original_dict = {"x": {"y": [1]}}
        state_with_copy = ImmutableState(original_dict, copy_data=True)
        original_dict["x"]["y"].append(2)
        assert state_with_copy["x"]["y"] == [1]

        state_from_state = ImmutableState(state_with_copy, copy_data=True)
        assert state_from_state["x"] == state_with_copy["x"]
        assert state_from_state["x"] is not state_with_copy["x"]

        state_from_state_no_copy = ImmutableState(state_with_copy, copy_data=False)
        assert state_from_state_no_copy["x"] is state_with_copy["x"]

        inner_list = [1]
        state_without_copy = ImmutableState({"l": inner_list}, copy_data=False)
        assert state_without_copy["l"] is inner_list

    def test_getitem(self) -> None:
        state = ImmutableState({"a": 1, "b": {"c": 2}})
        assert state["a"] == 1
        assert state["b"] == {"c": 2}
        with pytest.raises(KeyError):
            _ = state["missing"]

    def test_getattr(self) -> None:
        state = ImmutableState({"a": 1, "b": {"c": 2}})
        assert state.a == 1
        assert state.b == {"c": 2}
        with pytest.raises(AttributeError, match="missing"):
            _ = state.missing

    def test_getattr_slots_priority(self) -> None:
        state = ImmutableState({"_data": "val"})
        assert isinstance(state._data, dict)

    def test_iter_len_bool(self) -> None:
        state = ImmutableState({"a": 1, "b": 2})
        assert list(state) == ["a", "b"]
        assert len(state) == 2
        assert bool(state) is True
        assert bool(ImmutableState({})) is False

    def test_repr(self) -> None:
        assert repr(ImmutableState({"a": 1})) == "ImmutableState({'a': 1})"
        assert repr(ImmutableState({})) == "ImmutableState({})"

        class SubState(ImmutableState):
            pass

        assert repr(SubState({"a": 1})).startswith("SubState(")

    def test_as_dict(self) -> None:
        state = ImmutableState({"x": {"y": 1}})
        result_dict = state.as_dict()
        assert result_dict == {"x": {"y": 1}}
        assert result_dict["x"] is state["x"]
        result_dict["new"] = 2
        assert "new" not in state

    def test_copy(self) -> None:
        original_state = ImmutableState({"x": [1]})
        copied_state = copy(original_state)
        assert copied_state is not original_state
        assert copied_state == original_state
        assert copied_state["x"] is original_state["x"]

        class SubState(ImmutableState):
            pass

        assert type(copy(SubState({"a": 1}))) is SubState

    def test_deepcopy_raises(self) -> None:
        with pytest.raises(TypeError):
            deepcopy(ImmutableState({"a": 1}))

    def test_immutability(self) -> None:
        state = ImmutableState({"a": 1})
        with pytest.raises(TypeError):
            state["a"] = 2
        with pytest.raises(TypeError):
            state["b"] = 2
        with pytest.raises(AttributeError):
            state.a = 2
        with pytest.raises(AttributeError):
            state.b = 2

    def test_mutable_copy(self) -> None:
        immutable = ImmutableState({"a": [1, 2]})
        mutable = immutable.mutable_copy()

        assert isinstance(mutable, State)
        assert dict(mutable) == {"a": [1, 2]}

        mutable["a"].append(3)
        mutable["b"] = 4
        assert immutable["a"] == [1, 2]
        assert "b" not in immutable


class TestState:
    def test_init_default(self) -> None:
        state = State()
        assert dict(state) == {}
        assert len(state) == 0
        assert bool(state) is False

    @pytest.mark.parametrize(
        "input_data, expected_dict",
        [
            ({"a": 1, "b": 2}, {"a": 1, "b": 2}),
            ({}, {}),
            (_CustomMapping({"a": 1}), {"a": 1}),
            ([("a", 1)], {"a": 1}),
            (ImmutableState({"a": 1}), {"a": 1}),
            (State({"a": 1}), {"a": 1}),
        ],
    )
    def test_init_types(self, input_data: Any, expected_dict: dict[str, Any]) -> None:
        assert dict(State(input_data)) == expected_dict

    @pytest.mark.parametrize("invalid_value", [42])
    def test_init_invalid(self, invalid_value: Any) -> None:
        with pytest.raises(StateException, match="Invalid state type"):
            State(invalid_value)

    def test_copy_data(self) -> None:
        original_dict = {"x": {"y": [1]}}
        state_with_copy = State(original_dict, copy_data=True)
        original_dict["x"]["y"].append(2)
        assert state_with_copy["x"]["y"] == [1]

        state_with_copy["b"] = 2
        assert "b" not in original_dict

        inner_list = [1]
        state_without_copy = State({"l": inner_list}, copy_data=False)
        assert state_without_copy["l"] is inner_list

    def test_getitem(self) -> None:
        state = State({"a": 1, "b": {"c": 2}})
        assert state["a"] == 1
        assert state["b"] == {"c": 2}
        with pytest.raises(KeyError):
            _ = state["missing"]

    def test_getattr(self) -> None:
        state = State({"a": 1, "b": {"c": 2}})
        assert state.a == 1
        assert state.b == {"c": 2}
        with pytest.raises(AttributeError, match="missing"):
            _ = state.missing

    def test_getattr_slots_priority(self) -> None:
        state = State({"_data": "val"})
        assert isinstance(state._data, dict)

    def test_mutation(self) -> None:
        state = State({"a": 1})

        state["b"] = 2
        assert state["b"] == 2
        assert state.b == 2

        state.a = 99
        assert state["a"] == 99
        assert state.a == 99

        del state["b"]
        assert "b" not in state
        del state.a
        assert "a" not in state

        with pytest.raises(KeyError):
            del state["missing"]
        with pytest.raises(AttributeError, match="missing"):
            del state.missing

    def test_setattr_reserved_raises(self) -> None:
        state = State({"a": 1})
        with pytest.raises(AttributeError, match="_data"):
            state._data = {}
        with pytest.raises(AttributeError, match="_proxy"):
            state._proxy = None

    def test_iter_len_bool(self) -> None:
        state = State({"a": 1, "b": 2})
        assert list(state) == ["a", "b"]
        assert len(state) == 2
        assert bool(state) is True
        assert bool(State()) is False

    def test_repr(self) -> None:
        assert repr(State({"a": 1})) == "State({'a': 1})"
        assert repr(State()) == "State({})"

    def test_copy(self) -> None:
        original = State({"x": [1]})

        copied = copy(original)
        assert copied is not original
        assert copied == original
        assert copied["x"] is original["x"]

        method_copied = original.copy()
        assert method_copied is not original
        assert method_copied == original
        assert method_copied["x"] is original["x"]

        class SubState(State):
            pass

        sub = SubState({"a": 1})
        assert type(copy(sub)) is SubState
        assert type(sub.copy()) is SubState

    def test_immutable_copy(self) -> None:
        state = State({"a": [1, 2]})
        immutable = state.immutable_copy()

        assert isinstance(immutable, ImmutableState)
        assert dict(immutable) == {"a": [1, 2]}

        state["a"].append(3)
        assert immutable["a"] == [1, 2]

        with pytest.raises(TypeError):
            immutable["a"] = 2
        with pytest.raises(AttributeError):
            immutable.a = 2


class TestAddress:
    def test_basic_fields(self) -> None:
        host, port = "127.0.0.1", 8000
        addr = Address(host, port)
        assert addr.host == host
        assert addr.port == port

    @pytest.mark.parametrize("port", [0, 65535], ids=["min", "max"])
    def test_port_boundary_values_are_valid(self, port: int) -> None:
        assert Address("0.0.0.0", port).port == port

    @pytest.mark.parametrize("port", [65536, -1], ids=["above_max", "negative"])
    def test_invalid_port_raises_overflow(self, port: int) -> None:
        with pytest.raises(OverflowError):
            Address("0.0.0.0", port)

    def test_repr_matches_namedtuple_style(self) -> None:
        addr = Address("127.0.0.1", 8000)
        assert repr(addr) == "Address(host='127.0.0.1', port=8000)"

    def test_repr_quotes_host_like_python_repr(self) -> None:
        addr = Address("it's-a-host", 80)
        assert repr(addr) == 'Address(host="it\'s-a-host", port=80)'

    def test_len_is_always_two(self) -> None:
        assert len(Address("h", 1)) == 2

    def test_indexing(self) -> None:
        addr = Address("127.0.0.1", 8000)
        assert addr[0] == "127.0.0.1"
        assert addr[1] == 8000

    def test_negative_indexing(self) -> None:
        addr = Address("127.0.0.1", 8000)
        assert addr[-1] == 8000
        assert addr[-2] == "127.0.0.1"

    def test_index_out_of_range_raises(self) -> None:
        addr = Address("127.0.0.1", 8000)
        with pytest.raises(IndexError):
            addr[2]
        with pytest.raises(IndexError):
            addr[-3]

    def test_unpacking(self) -> None:
        host, port = Address("127.0.0.1", 8000)
        assert host == "127.0.0.1"
        assert port == 8000

    def test_iteration_yields_host_then_port(self) -> None:
        addr = Address("127.0.0.1", 8000)
        assert list(addr) == ["127.0.0.1", 8000]

    def test_star_unpacking_into_tuple(self) -> None:
        addr = Address("127.0.0.1", 8000)
        assert (*addr,) == ("127.0.0.1", 8000)

    def test_equal_to_address_with_same_fields(self) -> None:
        assert Address("127.0.0.1", 8000) == Address("127.0.0.1", 8000)

    @pytest.mark.parametrize(
        "other",
        [Address("127.0.0.2", 8000), Address("127.0.0.1", 9000)],
        ids=["different_host", "different_port"],
    )
    def test_not_equal_when_a_field_differs(self, other: Address) -> None:
        assert Address("127.0.0.1", 8000) != other

    def test_equal_to_plain_tuple(self) -> None:
        assert Address("127.0.0.1", 8000) == ("127.0.0.1", 8000)
        assert ("127.0.0.1", 8000) == Address("127.0.0.1", 8000)

    def test_not_equal_to_mismatched_tuple(self) -> None:
        assert Address("127.0.0.1", 8000) != ("127.0.0.1", 9000)

    @pytest.mark.parametrize("other", [42, "127.0.0.1", None])
    def test_not_equal_to_unrelated_type(self, other: Any) -> None:
        assert Address("127.0.0.1", 8000) != other

    def test_hashable(self) -> None:
        hash(Address("127.0.0.1", 8000))

    def test_equal_addresses_hash_equal(self) -> None:
        assert hash(Address("127.0.0.1", 8000)) == hash(Address("127.0.0.1", 8000))

    def test_usable_as_dict_key(self) -> None:
        mapping = {Address("127.0.0.1", 8000): "primary"}
        assert mapping[Address("127.0.0.1", 8000)] == "primary"

    def test_usable_in_set_with_deduplication(self) -> None:
        addresses = {
            Address("127.0.0.1", 8000),
            Address("127.0.0.1", 8000),
            Address("127.0.0.1", 9000),
        }
        assert len(addresses) == 2

    @pytest.mark.parametrize(("field", "value"), [("host", "10.0.0.1"), ("port", 9000)])
    def test_setting_field_raises(self, field: str, value: Any) -> None:
        addr = Address("127.0.0.1", 8000)
        with pytest.raises(AttributeError):
            setattr(addr, field, value)

    def test_fields(self) -> None:
        assert Address("h", 1)._fields == ("host", "port")

    def test_field_defaults_is_empty(self) -> None:
        assert Address("h", 1)._field_defaults == {}

    def test_asdict(self) -> None:
        assert Address("127.0.0.1", 8000)._asdict() == {"host": "127.0.0.1", "port": 8000}

    def test_make(self) -> None:
        addr = Address._make(["127.0.0.1", 8000])
        assert addr == Address("127.0.0.1", 8000)
        assert isinstance(addr, Address)

    def test_make_wrong_length_raises(self) -> None:
        with pytest.raises(TypeError):
            Address._make(["only-one"])

    def test_replace_single_field(self) -> None:
        addr = Address("127.0.0.1", 8000)
        replaced = addr._replace(port=9000)
        assert replaced == Address("127.0.0.1", 9000)
        assert addr == Address("127.0.0.1", 8000)

    def test_replace_no_kwargs_returns_equal_copy(self) -> None:
        addr = Address("127.0.0.1", 8000)
        assert addr._replace() == addr

    @pytest.mark.parametrize(
        ("kwargs", "expected_message"),
        [
            ({"bogus": 1}, r"Got unexpected field names: \['bogus'\]"),
            ({"bogus": 1, "another": 2}, r"Got unexpected field names: \['bogus', 'another'\]"),
            ({"port": 99, "bogus": 1}, r"Got unexpected field names: \['bogus'\]"),
        ],
        ids=["single_unexpected", "multiple_unexpected", "mixed_valid_and_invalid"],
    )
    def test_replace_unexpected_fields_raise(self, kwargs: dict[str, Any], expected_message: str) -> None:
        with pytest.raises(TypeError, match=expected_message):
            Address("h", 1)._replace(**kwargs)

    def test_dunder_replace_matches_replace(self) -> None:
        addr = Address("h", 1)
        assert addr.__replace__(port=99) == addr._replace(port=99) == Address("h", 99)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="copy.replace() was added in Python 3.13")
    def test_copy_replace_integration(self) -> None:
        import copy as copy_module

        addr = Address("h", 1)
        assert copy_module.replace(addr, port=99) == Address("h", 99)

    def test_count(self) -> None:
        addr = Address("127.0.0.1", 8000)
        assert addr.count("127.0.0.1") == 1
        assert addr.count("nope") == 0

    def test_index_found(self) -> None:
        assert Address("127.0.0.1", 8000).index("127.0.0.1") == 0
        assert Address("127.0.0.1", 8000).index(8000) == 1

    def test_index_not_found_raises(self) -> None:
        with pytest.raises(ValueError, match="not in tuple"):
            Address("127.0.0.1", 8000).index("missing")

    def test_index_respects_start_bound(self) -> None:
        with pytest.raises(ValueError, match="not in tuple"):
            Address("127.0.0.1", 8000).index("127.0.0.1", 1)

    @pytest.mark.parametrize(
        ("op", "a", "b", "expected"),
        [
            (operator.lt, Address("127.0.0.1", 8000), Address("127.0.0.1", 9000), True),
            (operator.lt, Address("127.0.0.1", 9000), Address("127.0.0.1", 8000), False),
            (operator.gt, Address("127.0.0.1", 9000), Address("127.0.0.1", 8000), True),
            (operator.le, Address("127.0.0.1", 8000), Address("127.0.0.1", 8000), True),
            (operator.ge, Address("127.0.0.1", 8000), Address("127.0.0.1", 8000), True),
            (operator.lt, Address("a", 9000), Address("b", 1000), True),
        ],
        ids=["lt_true", "lt_false", "gt_true", "le_equal", "ge_equal", "host_before_port"],
    )
    def test_comparison_operators(self, op: Any, a: Address, b: Address, expected: bool) -> None:
        assert op(a, b) is expected

    def test_sortable(self) -> None:
        addrs = [Address("127.0.0.1", 9000), Address("127.0.0.1", 8000)]
        assert sorted(addrs) == [Address("127.0.0.1", 8000), Address("127.0.0.1", 9000)]

    def test_compares_against_plain_tuple(self) -> None:
        assert Address("127.0.0.1", 8000) < ("127.0.0.1", 9000)
        assert ("127.0.0.1", 9000) > Address("127.0.0.1", 8000)

    def test_incomparable_type_raises_naming_address_not_tuple(self) -> None:
        with pytest.raises(TypeError, match="Address"):
            Address("127.0.0.1", 8000) < 42


class TestURL:
    def _check_url(self, url: URL) -> None:
        assert url.scheme == "https"
        assert url.hostname == "example.org"
        assert url.port == 8000
        assert url.netloc == "example.org:8000"
        assert url.username is None
        assert url.password is None
        assert url.path == "/path/to/somewhere"
        assert url.query == "abc=123"
        assert url.fragment == "anchor"

    def test_url(self) -> None:
        url = URL("https://example.org:8000/path/to/somewhere?abc=123#anchor")
        self._check_url(url)

        url_path = URLPath("/path/to/somewhere?abc=123#anchor", "https://example.org:8000")
        url = URL(url_path)
        self._check_url(url)

    def test_replace(self) -> None:
        url = URL("https://example.org:8000/path/to/somewhere?abc=123#anchor")
        new_url = url.replace(scheme="http")
        assert new_url == "http://example.org:8000/path/to/somewhere?abc=123#anchor"
        assert new_url.scheme == "http"

        new_url = url.replace(port=None)
        assert new_url == "https://example.org/path/to/somewhere?abc=123#anchor"
        assert new_url.port is None

        new_url = url.replace(hostname="example.com")
        assert new_url == "https://example.com:8000/path/to/somewhere?abc=123#anchor"
        assert new_url.hostname == "example.com"

        ipv6_url = URL("https://[fe::2]:12345")
        new_ipv6_url = ipv6_url.replace(port=8000)
        assert new_ipv6_url == "https://[fe::2]:8000"
        assert new_ipv6_url.port == 8000

        new_ipv6_url = ipv6_url.replace(username="username", password="password")
        assert new_ipv6_url == "https://username:password@[fe::2]:12345"
        assert new_ipv6_url.netloc == "username:password@[fe::2]:12345"
        assert new_ipv6_url.username == "username"
        assert new_ipv6_url.password == "password"

        ipv6_url = URL("https://[fe::2]")
        new_ipv6_url = ipv6_url.replace(port=8000)
        assert new_ipv6_url == "https://[fe::2]:8000"
        assert new_ipv6_url.port == 8000

        url = URL("http://u:p@host/")
        new_url = url.replace(hostname="foo")
        assert new_url == "http://u:p@foo/"
        assert new_url.hostname == "foo"

        url = URL("http://host:80")
        new_url = url.replace(username="user")
        assert new_url == "http://user@host:80"

    def test_url_eq(self) -> None:
        assert URL("") == URL("")
        assert URL("/foo") == "/foo"
        assert URL("") != 1

    def test_url_repr(self) -> None:
        url = URL("https://example.org:8000/path/to/somewhere?abc=123#anchor")
        assert repr(url) == "URL('https://example.org:8000/path/to/somewhere?abc=123#anchor')"

    def test_url_replace_query_params(self) -> None:
        url = URL("https://example.org:8000/path/to/somewhere?abc=123#anchor")
        assert url.query == "abc=123"
        url = url.replace_query_params(order="name")
        assert url == "https://example.org:8000/path/to/somewhere?order=name#anchor"
        assert url.query == "order=name"

    def test_url_remove_query_params(self) -> None:
        url = URL("https://example.org/path/to?a=1&b=2")
        assert url.query == "a=1&b=2"
        url = url.remove_query_params("a")
        assert url == "https://example.org/path/to?b=2"
        assert url.query == "b=2"
        url = URL("https://example.org/path/to?a=1&b=2&c=3")
        url = url.remove_query_params(("a", "b", "c"))
        assert url == "https://example.org/path/to"
        assert url.query == ""

    def test_url_include_query_params(self) -> None:
        url = URL("https://example.org/path/to?a=1")
        assert url.query == "a=1"
        url = url.include_query_params(a=2)
        assert url.query == "a=2"
        assert url == "https://example.org/path/to?a=2"
        url = url.include_query_params(search="test")
        assert url.query == "a=2&search=test"
        assert url == "https://example.org/path/to?a=2&search=test"

    def test_hidden_password(self) -> None:
        url = URL("https://example.org/path/to?a=1")
        assert repr(url) == "URL('https://example.org/path/to?a=1')"
        url = URL("https://username@example.org/path/to?a=1")
        assert repr(url) == "URL('https://username@example.org/path/to?a=1')"
        url = URL("https://username:password@example.org/path/to?a=1")
        assert repr(url) == "URL('https://username:**********@example.org/path/to?a=1')"


class TestURLPath:
    @pytest.mark.parametrize(
        'base, path', [
            ('http://example.org', 'foo/bar?a=1&b=2'),
            ('http://example.org/', 'foo/bar?a=1&b=2'),
            ('http://example.org', '/foo/bar?a=1&b=2'),
            ('http://example.org', '/foo/bar?a=1&b=2')
        ]
    )
    def test_url_path(self, base: str, path: str) -> None:
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
    def test_url_path_repr(self, base: str, path: str) -> None:
        assert repr(URLPath(path, base)) == f"URLPath(path={path!r}, base={base!r})"

    def test_matches_str(self) -> None:
        url_path = URLPath("/foo/bar?a=1", "https://example.org:8000")
        assert url_path.make_absolute_url() == str(url_path)

    def test_returns_url(self) -> None:
        url_path = URLPath("/foo/bar?a=1", "https://example.org:8000")
        result = url_path.make_absolute_url()
        assert isinstance(result, URL)
        assert result.scheme == "https"
        assert result.path == "/foo/bar"
        assert result.query == "a=1"

    def test_overrides_base_url(self) -> None:
        url_path = URLPath("/foo", "https://example.org")
        other = URL("http://other.example:9000")
        assert url_path.make_absolute_url(base_url=other) == "http://other.example:9000/foo"

    def test_overrides_base_str(self) -> None:
        url_path = URLPath("/foo", "https://example.org")
        assert url_path.make_absolute_url(base_url="https://third.example") == "https://third.example/foo"

    def test_base_not_mutated(self) -> None:
        url_path = URLPath("/foo", "https://example.org")
        url_path.make_absolute_url(base_url="https://other.example")
        assert str(url_path) == "https://example.org/foo"
        assert str(url_path.base) == "https://example.org"


class TestHeaders:
    def test_headers(self) -> None:
        headers = Headers(raw=[(b"a", b"123"), (b"a", b"456"), (b"b", b"789")])
        assert "a" in headers
        assert "A" in headers
        assert "b" in headers
        assert "B" in headers
        assert "c" not in headers

    def test_headers_to_mapper(self) -> None:
        headers = Headers(raw=[(b"a", b"123"), (b'a', b"456"), (b"b", b"789")])
        assert headers["a"] == "123"
        assert headers.get("a") == "123"
        assert headers.get("null") is None
        assert headers.getlist("a") == sorted(["123", "456"])
        assert headers.keys() == ["a", "a", "b"]
        assert headers.values() == ["123", "456", "789"]
        assert headers.items() == [("a", "123"), ("a", "456"), ("b", "789")]
        assert list(headers) == ["a", "a", "b"]
        assert dict(headers) == {"a": "123", "b": "789"}

    def test_headers_eq(self) -> None:
        headers = Headers(raw=[(b"a", b"123"), (b"a", b"456"), (b"b", b"789")])
        assert headers == Headers(raw=[(b"a", b"123"), (b"a", b"456"), (b"b", b"789")])
        assert headers != [(b"a", b"123"), (b"a", b"456"), (b"b", b"789")]
        assert headers != Headers(raw=[(b"a", b"123"), (b"a", b"456"), (b"b", b"789"), (b"c", b"455")])

    def test_headers_repr(self) -> None:
        headers = Headers({"a": "123", "b": "789"})
        assert repr(headers) == "Headers({'a': '123', 'b': '789'})"
        headers = Headers(raw=[(b"a", b"123"), (b"a", b"456"), (b"b", b"789")])
        assert repr(headers) == "Headers(raw=[(b'a', b'123'), (b'a', b'456'), (b'b', b'789')])"

    def test_headers_raw(self) -> None:
        headers = Headers({"a": "123", "b": "789"})
        assert headers["a"] == "123"
        assert headers["A"] == "123"
        assert headers["b"] == "789"
        assert headers.raw == [(b"a", b"123"), (b"b", b"789")]

    def test_headers_mutablecopy(self) -> None:
        headers = Headers(raw=[(b"a", b"123"), (b"a", b"456"), (b"b", b"789")])
        headers_copy = headers.mutablecopy()
        assert headers_copy.items() == [("a", "123"), ("a", "456"), ("b", "789")]
        headers_copy["a"] = "346"
        assert headers_copy.items() == [("a", "346"), ("b", "789")]
        assert headers_copy != headers

    def test_headers_from_scope(self) -> None:
        headers = Headers(scope={"headers": ((b"a", b"1"),)})
        assert dict(headers) == {"a": "1"}
        assert list(headers.items()) == [("a", "1")]
        assert list(headers.raw) == [(b"a", b"1")]

        headers = Headers.from_scope(scope={"headers": ((b"a", b"1"),)})
        assert dict(headers) == {"a": "1"}
        assert list(headers.items()) == [("a", "1")]
        assert list(headers.raw) == [(b"a", b"1")]


class TestMutableHeaders:
    def test_mutable_headers(self) -> None:
        headers = MutableHeaders()
        assert dict(headers) == {}
        headers["a"] = "1"
        assert dict(headers) == {"a": "1"}
        headers["a"] = "2"
        assert dict(headers) == {"a": "2"}
        headers.setdefault("a", "3")
        assert dict(headers) == {"a": "2"}
        headers.setdefault("b", "4")
        assert dict(headers) == {"a": "2", "b": "4"}
        del headers["a"]
        assert dict(headers) == {"b": "4"}
        assert headers.raw == [(b"b", b"4")]

    @pytest.mark.parametrize(
        "value", (
                MutableHeaders({"a": "1"}),
                {"a": "1"},
        ),
    )
    def test_mutable_headers_merge(self, value: MutableHeaders | dict[str, str]) -> None:
        headers = MutableHeaders()
        headers = headers | value
        assert isinstance(headers, MutableHeaders)
        assert dict(headers) == {"a": "1"}
        assert headers.items() == [("a", "1",)]
        assert headers.raw == [(b"a", b"1")]

    @pytest.mark.parametrize(
        "value", (
                MutableHeaders({"a": "1"}),
                {"a": "1"},
        ),
    )
    def test_mutable_headers_update(self, value: MutableHeaders | dict[str, str]) -> None:
        headers = MutableHeaders()
        headers |= value
        assert isinstance(headers, MutableHeaders)
        assert dict(headers) == {"a": "1"}
        assert headers.items() == [("a", "1",)]
        assert headers.raw == [(b"a", b"1",)]

    def test_mutable_headers_merge_not_mapping(self) -> None:
        headers = MutableHeaders()
        with pytest.raises(TypeError):
            headers |= {"error"}
        with pytest.raises(TypeError):
            headers | {"error"}

    def test_mutable_headers_from_scope(self) -> None:
        headers = MutableHeaders(scope={"headers": ((b"a", b"1"),)})
        assert dict(headers) == {"a": "1"}
        headers.update({"b": "2"})
        assert dict(headers) == {"a": "1", "b": "2"}
        assert list(headers.items()) == [("a", "1"), ("b", "2",)]
        assert list(headers.raw) == [(b"a", b"1"), (b"b", b"2")]


class TestImmutableMultiDict:
    def test_immutable_multidict_getList(self) -> None:
        multidict = ImmutableMultiDict([('a', '123'), ('a', '456'), ('b', '789')], c='12')
        assert isinstance(multidict.getList('a'), list)
        assert multidict.getList('a') == ['123', '456']
        assert multidict.getList('b') == ['789']
        assert multidict.getList('c') == ['12']

    def test_immutable_multidict_multi_items(self) -> None:
        multidict = ImmutableMultiDict([('a', '123'), ('a', '456'), ('b', '789')], c='12')
        items = multidict.multi_items()
        assert isinstance(items, list)
        assert len(items) > 1
        assert sorted(items) == sorted([('a', '123'), ('a', '456'), ('b', '789'), ('c', '12')])

    def test_immutable_multidict(self) -> None:
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


class TestMultiDict:
    def test_multidict(self) -> None:
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

    def test_multidict_update(self) -> None:
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

    def test_multidict_append(self) -> None:
        multidict = MultiDict([('a', '123')])
        multidict.append('a', '456')
        assert multidict.getList('a') == ['123', '456']
        assert repr(multidict) == "MultiDict([('a', '123'), ('a', '456')])"

    def test_multidict_setdefault(self) -> None:
        multidict = MultiDict([('a', '123')])
        assert multidict.setdefault('a', '456') == '123'
        assert multidict.getList('a') == ['123']
        assert multidict.setdefault('b', '456') == '456'
        assert multidict.getList('b') == ['456']
        assert repr(multidict) == "MultiDict([('a', '123'), ('b', '456')])"

    def test_multidict_setlist(self) -> None:
        multidict = MultiDict([('a', '123')])
        multidict.setlist('a', ['456', '789'])
        assert multidict.getList('a') == ['456', '789']
        multidict.setlist('b', [])
        assert 'b' not in multidict

    def test_multidict_clear(self) -> None:
        multidict = MultiDict([('a', '123'), ('a', '456'), ('b', '789')])
        multidict.clear()
        assert multidict.get('a') is None
        assert repr(multidict) == 'MultiDict([])'

    def test_multidict_poplist(self) -> None:
        multidict = MultiDict([('a', '123'), ('a', '456'), ('b', '789')])
        assert multidict.poplist('a') == ['123', '456']
        assert multidict.get('a') is None
        assert repr(multidict) == "MultiDict([('b', '789')])"

    def test_multidict_popitem(self) -> None:
        multidict = MultiDict([('a', '123'), ('a', '456'), ('b', '789')])
        item = multidict.popitem()
        assert multidict.get(item[0]) is None

    def test_multidict_pop(self) -> None:
        multidict = MultiDict([('a', '123'), ('a', '456'), ('b', '789')])
        assert multidict.pop('a') == '456'
        assert multidict.get('a') is None
        assert repr(multidict) == "MultiDict([('b', '789')])"

    def test_multidict_del(self) -> None:
        multidict = MultiDict([('a', '123'), ('a', '456',)])
        del multidict['a']
        assert multidict.get('a') is None
        assert repr(multidict) == 'MultiDict([])'

    def test_multidict_get(self) -> None:
        multidict = MultiDict([('a', '123'), ('a', '456',)])
        multidict['a'] = '789'
        assert multidict['a'] == '789'
        assert multidict.get('a') == '789'
        assert multidict.getList('a') == ['789']

    def test_multidict_eq(self) -> None:
        multidict = MultiDict([('a', '123'), ('a', '456',)])
        assert MultiDict(multidict) == multidict


class TestQueryParams:
    def test_query_params(self) -> None:
        query = QueryParams('a=123&a=456&b=789')
        assert 'a' in query
        assert 'A' not in query
        assert 'c' not in query
        assert query['a'] == '456'
        assert query.get('nope') is None
        assert sorted(query.getList('a')) == sorted(['123', '456'])
        assert sorted(query.items()) == sorted([('a', '456'), ('b', '789')])
        assert repr(query) == "QueryParams('a=123&a=456&b=789')"

    def test_query_params_repr(self) -> None:
        query = QueryParams('a=123&b=456')

        assert repr(query) == "QueryParams('a=123&b=456')"
        query = QueryParams({'a': '123', 'b': '456'})
        assert repr(query) == "QueryParams('a=123&b=456')"
        query = QueryParams([('a', 123), ('b', 456)])
        assert repr(query) == "QueryParams('a=123&b=456')"

    def test_query_params_eq(self) -> None:
        assert QueryParams({'a': '123', 'b': '456'}) == QueryParams([('a', '123'), ('b', '456')])

        assert QueryParams({'a': '123', 'b': '456'}) == QueryParams({'a': '123', 'b': '456'})
        assert QueryParams({'a': '123', 'b': '456'}) == QueryParams('a=123&b=456')
        assert QueryParams({'a': '123', 'b': '456'}) == QueryParams({'b': '456', 'a': '123'})
        assert QueryParams() == QueryParams([])
        assert QueryParams([('a', '123'), ('a', '456')]) == QueryParams('a=123&a=456')
        assert QueryParams({'a': '123', 'b': '456'}) != 'null'
        query = QueryParams([('a', '123'), ('b', '456')])
        assert QueryParams(query) == query

    def test_url_blank_params(self) -> None:
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


class TestUploadFile:
    async def test_upload_file_input(self) -> None:
        file = UploadFile(filename='file', file_data=b'data')
        assert await file.read() == b'data'
        assert await file.size() == 4
        await file.write(b' and more data!')
        assert await file.read() == b''
        assert await file.size() == 19
        await file.seek(0)
        assert await file.read() == b'data and more data!'

    async def test_upload_file_rolling(self) -> None:
        file = UploadFile(filename='file', file_data=b'', size=0)
        assert await file.read() == b''
        assert await file.size() == 0
        await file.write(b'data')
        assert file.is_spooled_to_disk
        assert await file.read() == b''
        assert await file.size() == 4
        await file.seek(0)
        assert await file.read() == b'data'
        await file.write(b' more')
        assert await file.read() == b''
        assert await file.size() == 9
        await file.seek(0)
        assert await file.read() == b'data more'
        assert await file.size() == 9
        await file.close()

    async def test_upload_file_repr(self) -> None:
        file = UploadFile(filename='file', file_data=b'', size=0)
        assert repr(file) == "UploadFile(filename='file', headers={})"
        file = UploadFile(filename='file', file_data=b'', size=0, headers={'content-type': 'video/mp4'})
        assert repr(file) == "UploadFile(filename='file', headers={'content-type': 'video/mp4'})"


class TestFormMultiDict:
    @pytest.mark.anyio
    async def test_form_multi_dict_close(self, mocker: MockFixture) -> None:
        close = mocker.patch('speedy.datastructures.UploadFile.close')

        multi = FormMultiDict(
            [
                ('foo', UploadFile(filename='foo')),
                ('bar', UploadFile(filename='bar')),
            ]
        )
        await multi.close()

        assert close.call_count == 2
