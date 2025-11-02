from typing import Annotated, List, Any, Dict

import pytest
from typing_extensions import Required, NotRequired, ReadOnly

from speedy.utils.typing import unwrap_annotation, get_origin_or_inner_type
from tests.models import DataclassUser


@pytest.mark.parametrize(
    "annotation, expected_core, expected_metadata, expected_wrappers",
    [
        (int, int, (), set()),
        (Annotated[int, "foo"], int, ("foo",), {Annotated}),
        (Annotated[str, "foo", 1], str, ("foo", 1), {Annotated}),
        (Required[int], int, (), {Required}),
        (NotRequired[str], str, (), {NotRequired}),
        (ReadOnly[bool], bool, (), {ReadOnly}),
        (List[int], List[int], (), set()),
    ],
)
def test_unwrap_annotation_simple_cases(
        annotation: Any,
        expected_core: Any,
        expected_metadata: tuple,
        expected_wrappers: set,
) -> None:
    core, metadata, wrappers = unwrap_annotation(annotation)
    assert core == expected_core
    assert metadata == expected_metadata
    assert wrappers == expected_wrappers


@pytest.mark.parametrize(
    "annotation, expected_core, expected_metadata, expected_wrappers",
    [
        (Annotated[Required[int], "positive"], int, ("positive",), {Annotated, Required}),
        (Required[Annotated[str, "non-empty"]], str, ("non-empty",), {Required, Annotated}),
        (
                ReadOnly[NotRequired[Annotated[Required[float], "currency"]]],
                float,
                ("currency",),
                {ReadOnly, NotRequired, Annotated, Required},
        ),
    ],
)
def test_unwrap_annotation_nested_cases(
        annotation: Any,
        expected_core: Any,
        expected_metadata: tuple,
        expected_wrappers: set,
) -> None:
    core, metadata, wrappers = unwrap_annotation(annotation)
    assert core == expected_core
    assert metadata == expected_metadata
    assert wrappers == expected_wrappers


@pytest.mark.parametrize(
    "annotation, expected_origin",
    [
        (List[DataclassUser], list),
        (Annotated[List[DataclassUser], "foo"], list),
        (Annotated[Dict[str, List[DataclassUser]], "foo"], dict),
    ],
)
def test_get_origin_or_inner_type(annotation: Any, expected_origin: Any) -> None:
    assert get_origin_or_inner_type(annotation) == expected_origin
