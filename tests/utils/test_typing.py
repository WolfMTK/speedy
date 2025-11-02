from typing import Annotated, List, Dict

from typing_extensions import Required, NotRequired, ReadOnly

from speedy.utils.typing import unwrap_annotation, get_origin_or_inner_type
from tests.models import DataclassUser


def test_unwrap_plain_type() -> None:
    result = unwrap_annotation(int)
    assert result == (int, (), set())


def test_unwrap_annotated_simple() -> None:
    result = unwrap_annotation(Annotated[int, "foo",])
    assert result == (int, ("foo",), {Annotated})


def test_unwrap_annotated_multiple_metadata() -> None:
    result = unwrap_annotation(Annotated[str, "foo", 1])
    assert result == (str, ("foo", 1), {Annotated})


def test_unwrap_required():
    result = unwrap_annotation(Required[int])
    assert result == (int, (), {Required})


def test_unwrap_notrequired():
    result = unwrap_annotation(NotRequired[str])
    assert result == (str, (), {NotRequired})


def test_unwrap_readonly():
    result = unwrap_annotation(ReadOnly[bool])
    assert result == (bool, (), {ReadOnly})


def test_unwrap_mixed_wrappers_annotated_outer() -> None:
    typ = Annotated[Required[int], "positive"]
    core, meta, wrappers = unwrap_annotation(typ)
    assert core == int
    assert meta == ("positive",)
    assert wrappers == {Annotated, Required}


def test_unwrap_mixed_wrappers_required_outer():
    typ = Required[Annotated[str, "non-empty"]]
    core, meta, wrappers = unwrap_annotation(typ)
    assert core == str
    assert meta == ("non-empty",)
    assert wrappers == {Required, Annotated}


def test_unwrap_deeply_nested():
    typ = ReadOnly[NotRequired[Annotated[Required[float], "currency"]]]
    core, meta, wrappers = unwrap_annotation(typ)
    assert core == float
    assert meta == ("currency",)
    assert wrappers == {ReadOnly, NotRequired, Annotated, Required}


def test_unwrap_non_wrapper_generic():
    result = unwrap_annotation(List[int])
    assert result == (List[int], (), set())


def test_get_origin_or_inner_type() -> None:
    assert get_origin_or_inner_type(List[DataclassUser]) == list
    assert get_origin_or_inner_type(Annotated[List[DataclassUser], "foo"]) == list
    assert get_origin_or_inner_type(Annotated[Dict[str, List[DataclassUser]], "foo"]) == dict
