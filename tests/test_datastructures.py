from copy import deepcopy, copy
from typing import Mapping, Any, Iterator

import pytest

from speedy.datastructures import ImmutableState, State
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
            _ =state.missing

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
