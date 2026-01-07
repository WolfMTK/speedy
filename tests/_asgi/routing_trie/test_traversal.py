import datetime
import decimal
import re
import uuid

import pytest
from typing_extensions import Any

from speedy._asgi.routing_trie import (
    parse_path_params,
    traverse_route_map,
    parse_node_handlers,
    parse_path_to_route,
)
from speedy._asgi.routing_trie.types import PathParameterSentinel, RouteTrieNode, ASGIHandlerTuple
from speedy.exceptions import NotFoundException, MethodNotAllowedException
from speedy.types import PathParameterDefinition


def test_parse_path_params_empty() -> None:
    result = parse_path_params((), ())
    assert result == {}


@pytest.mark.parametrize(
    "definition, value, expected",
    [
        (PathParameterDefinition("id", "id:int", int, int), "123", 123),
        (PathParameterDefinition("price", "p:float", float, float), "10.5", 10.5),
        (PathParameterDefinition("name", "n:str", str, None), "alice", "alice"),
    ],
)
def test_parse_path_params_single_param(
        definition: PathParameterDefinition,
        value: str,
        expected: Any,
) -> None:
    result = parse_path_params((definition,), (value,))
    assert result == {definition.name: expected}


def test_parse_path_params_mixed_params() -> None:
    params = (
        PathParameterDefinition("id", "id:int", int, int),
        PathParameterDefinition("name", "n:str", str, None),
        PathParameterDefinition("active", "a:bool", bool, lambda x: x == "true"),
    )
    values = ("42", "bob", "true")

    result = parse_path_params(params, values)

    assert result == {
        "id": 42,
        "name": "bob",
        "active": True,
    }


@pytest.mark.parametrize(
    "definition, value",
    [
        (PathParameterDefinition("id", "id:int", int, int), "not-a-number"),
        (PathParameterDefinition("dt", "d:date", datetime.date, datetime.date.fromisoformat), "2023-13-01"),
    ],
)
def test_parse_path_params_parser_error(
        definition: PathParameterDefinition,
        value: str,
) -> None:
    with pytest.raises(ValueError):
        parse_path_params((definition,), (value,))


def test_parse_path_params_mismatched_length() -> None:
    params = (
        PathParameterDefinition("a", "a:int", int, int),
        PathParameterDefinition("b", "b:int", int, int),
    )
    values = ("1",)

    result = parse_path_params(params, values)
    assert result == {"a": 1}
    assert "b" not in result


def test_parse_path_params_complex_types():
    uid_str = str(uuid.uuid4())
    params = (
        PathParameterDefinition("uid", "uid:uuid", uuid.UUID, uuid.UUID),
        PathParameterDefinition("date", "d:date", datetime.date, datetime.date.fromisoformat),
        PathParameterDefinition("decimal", "dec:decimal", decimal.Decimal, decimal.Decimal),
    )
    values = (uid_str, "2023-01-01", "10.55")

    result = parse_path_params(params, values)

    assert isinstance(result["uid"], uuid.UUID)
    assert result["uid"] == uuid.UUID(uid_str)
    assert result["date"] == datetime.date(2023, 1, 1)
    assert result["decimal"] == decimal.Decimal("10.55")


def test_parse_path_params_caching():
    params = (PathParameterDefinition("id", "id:int", int, int),)
    values = ("42",)

    res1 = parse_path_params(params, values)
    res2 = parse_path_params(params, values)

    assert res1 is res2
    assert res1 == {"id": 42}


def create_node(**kwargs: Any) -> RouteTrieNode:
    defaults = {
        "child_keys": set(),
        "children": {},
        "is_path_param_node": False,
        "is_path_type": False,
        "asgi_handlers": {},
        "is_asgi": False,
        "is_mount": False,
        "path_parameters": {},
        "path_template": "",
    }
    return RouteTrieNode(**{**defaults, **kwargs})


def test_traverse_static_path() -> None:
    leaf_node = create_node(asgi_handlers={"GET": None})
    mid_node = create_node(
        child_keys={"leaf"},
        children={"leaf": leaf_node},
    )
    root = create_node(
        child_keys={"mid"},
        children={"mid": mid_node},
    )

    result_node, params, result_path = traverse_route_map(root, "/mid/leaf")

    assert result_node is leaf_node
    assert params == []
    assert result_path == "/mid/leaf"


def test_traverse_single_param() -> None:
    leaf_node = create_node(asgi_handlers={"GET": None})

    param_node = create_node(
        is_path_param_node=True,
        is_path_type=False,
        child_keys={PathParameterSentinel},
        children={PathParameterSentinel: leaf_node},
    )

    root = create_node(
        child_keys={"users"},
        children={"users": param_node},
    )

    result_node, params, result_path = traverse_route_map(root, "/users/123")

    assert result_node is leaf_node
    assert params == ["123"]
    assert result_path == "/users/123"


def test_traverse_path_type_parameter() -> None:
    leaf_node = create_node(asgi_handlers={"GET": None})

    param_node = create_node(
        is_path_param_node=True,
        is_path_type=True,
        child_keys={PathParameterSentinel},
        children={PathParameterSentinel: leaf_node},
    )

    root = create_node(
        child_keys={"files"},
        children={"files": param_node},
    )

    path = "/files/a/b/c.txt"
    result_node, params, result_path = traverse_route_map(root, path)

    assert result_node is leaf_node
    assert len(params) == 1
    assert params[0] == "/a/b/c.txt"
    assert result_path == path


def test_traverse_mixed_static_and_param() -> None:
    leaf_node = create_node(asgi_handlers={"GET": None})

    param_node = create_node(
        is_path_param_node=True,
        child_keys={PathParameterSentinel},
        children={PathParameterSentinel: leaf_node},
    )

    root = create_node(
        child_keys={"api"},
        children={"api": param_node},
    )

    result_node, params, _ = traverse_route_map(root, "/api/v1")

    assert result_node is leaf_node
    assert params == ["v1"]


def test_traverse_not_found_invalid_segment() -> None:
    root = create_node(child_keys={"api"}, children={"api": create_node()})

    with pytest.raises(NotFoundException):
        traverse_route_map(root, "/invalid")


def test_traverse_not_found_no_handlers() -> None:
    root = create_node(
        child_keys={"api"},
        children={"api": create_node(asgi_handlers={})},
    )

    with pytest.raises(NotFoundException):
        traverse_route_map(root, "/api")


def test_traverse_empty_path_to_root() -> None:
    root = create_node(asgi_handlers={"GET": None})

    result_node, params, _ = traverse_route_map(root, "/")

    assert result_node is root
    assert params == []


def test_traverse_path_type_trailing_slash() -> None:
    leaf_node = create_node(asgi_handlers={"GET": None})
    param_node = create_node(
        is_path_param_node=True,
        is_path_type=True,
        child_keys={PathParameterSentinel},
        children={PathParameterSentinel: leaf_node},
    )
    root = create_node(
        child_keys={"static"},
        children={"static": param_node},
    )
    result_node, params, _ = traverse_route_map(root, "/static/foo/bar/")

    assert result_node is leaf_node
    assert params == ["/foo/bar"]


def test_parse_node_handlers_http_method() -> None:
    node = create_node(asgi_handlers={"GET": ASGIHandlerTuple("app", "handler")})
    app, handler = parse_node_handlers(node, "GET")
    assert app == "app"
    assert handler == "handler"


def test_parse_node_handlers_websocket() -> None:
    node = create_node(asgi_handlers={"websocket": ASGIHandlerTuple("app", "ws_handler")})
    app, handler = parse_node_handlers(node, None)
    assert app == "app"
    assert handler == "ws_handler"


def test_parse_node_handlers_asgi_node() -> None:
    node = create_node(
        is_asgi=True,
        asgi_handlers={"asgi": ASGIHandlerTuple("app", "asgi_handler")},
    )
    app, handler = parse_node_handlers(node, "GET")
    assert app == "app"


def test_parse_node_handlers_method_not_allowed() -> None:
    node = create_node(asgi_handlers={"GET": ASGIHandlerTuple(None, None)})
    with pytest.raises(MethodNotAllowedException) as exc:
        parse_node_handlers(node, "POST")
    assert exc.value.headers["allow"] == "GET"


def test_parse_path_to_route_plain_route() -> None:
    leaf_handler = ASGIHandlerTuple("app", "handler")
    leaf_node = create_node(asgi_handlers={"GET": leaf_handler})

    root = create_node(
        child_keys={"/plain"},
        children={"/plain": leaf_node},
    )

    app, handler, path, params, template = parse_path_to_route(
        method="GET",
        mount_paths_regex=None,
        mount_routes={},
        path="/plain",
        plain_routes={"/plain"},
        root_node=root,
    )

    assert app == "app"
    assert handler == "handler"
    assert path == "/plain"
    assert params == {}


def test_parse_path_to_route_mount_point_hit() -> None:
    mount_handler = ASGIHandlerTuple("mount_app", "mount_handler")
    mount_node = create_node(
        is_mount=True,
        asgi_handlers={"GET": mount_handler},
        children={"/sub": create_node()},
    )

    root = create_node(path_template="/root_tmpl")

    regex = re.compile(r"^/mount")
    mount_routes = {"/mount": mount_node}
    app, handler, path, params, template = parse_path_to_route(
        method="GET",
        mount_paths_regex=regex,
        mount_routes=mount_routes,
        path="/mount/orphan",
        plain_routes=set(),
        root_node=root,
    )

    assert app == "mount_app"
    assert path == "/orphan/"
    assert template == "/root_tmpl"


def test_parse_path_to_route_mount_root_hit() -> None:
    mount_handler = ASGIHandlerTuple("mount_app", "mount_handler")
    mount_node = create_node(is_mount=True, asgi_handlers={"GET": mount_handler})
    root = create_node(path_template="/tmpl")

    regex = re.compile(r"^/mount")
    mount_routes = {"/mount": mount_node}

    app, handler, path, params, template = parse_path_to_route(
        method="GET",
        mount_paths_regex=regex,
        mount_routes=mount_routes,
        path="/mount",
        plain_routes=set(),
        root_node=root,
    )

    assert app == "mount_app"
    assert path == "/"
