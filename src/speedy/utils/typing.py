from collections import defaultdict, deque, abc
from typing import (
    Any,
    get_origin,
    AbstractSet,
    DefaultDict,
    Deque,
    Dict,
    FrozenSet,
    List,
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
    Sequence,
    Set,
    Tuple,
    get_args,
    Annotated,
)

from typing_extensions import Required, NotRequired, ReadOnly

wrapper_type_set = {Annotated, Required, NotRequired, ReadOnly}

instantiable_type_mapping = {
    AbstractSet: set,
    DefaultDict: defaultdict,
    Deque: deque,
    Dict: dict,
    FrozenSet: frozenset,
    List: list,
    Mapping: dict,
    MutableMapping: dict,
    MutableSequence: list,
    MutableSet: set,
    Sequence: list,
    Set: set,
    Tuple: tuple,
    abc.Mapping: dict,
    abc.MutableMapping: dict,
    abc.MutableSequence: list,
    abc.MutableSet: set,
    abc.Sequence: list,
    abc.Set: set,
    defaultdict: defaultdict,
    deque: deque,
    dict: dict,
    frozenset: frozenset,
    list: list,
    set: set,
    tuple: tuple,
}


def unwrap_annotation(annotation: Any) -> tuple[Any, tuple[Any, ...], set[Any],]:
    """ Remove "wrapper" annotation types. """
    origin = get_origin(annotation)
    wrappers = set()
    metadata = []
    while origin in wrapper_type_set:
        wrappers.add(origin)
        annotation, *meta = get_args(annotation)
        metadata.extend(meta)
        origin = get_origin(annotation)
    return annotation, tuple(metadata), wrappers


def get_origin_or_inner_type(annotation: Any) -> Any:
    """ Get origin or unwrap it. Returns None for non-generic types. """
    origin = get_origin(annotation)
    if origin in wrapper_type_set:
        inner, _, _ = unwrap_annotation(annotation)
        origin = get_origin_or_inner_type(inner)
    return instantiable_type_mapping.get(origin, origin)
