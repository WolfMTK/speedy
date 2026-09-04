import operator
import sys
from copy import copy, deepcopy
from typing import Any, Iterator, Mapping

import pytest

from speedy.datastructures import Address, ImmutableState, State
from speedy.exceptions import StateException


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
        assert repr(addr) == "Address(host=\"it's-a-host\", port=80)"

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
