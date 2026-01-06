import pytest

from speedy._asgi.routing_trie import create_node, validate_node
from speedy._asgi.routing_trie.types import ASGIHandlerTuple
from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.types import PathParameterDefinition


def test_validate_node_valid_empty() -> None:
    node = create_node()
    validate_node(node)


def test_validate_node_valid_asgi_handler() -> None:
    node = create_node()
    node.is_asgi = True
    node.asgi_handlers = {"asgi": ASGIHandlerTuple(None, None)}
    validate_node(node)


def test_validate_node_invalid_asgi_mixed_handlers() -> None:
    node = create_node()
    node.is_asgi = True
    node.asgi_handlers = {
        "asgi": ASGIHandlerTuple(None, None),
        "GET": ASGIHandlerTuple(None, None),
    }
    with pytest.raises(ImproperlyConfiguredException) as exc:
        validate_node(node)
    assert "unique path" in str(exc.value)


def test_validate_node_invalid_asgi_http_only() -> None:
    node = create_node()
    node.is_asgi = True
    node.asgi_handlers = {"GET": ASGIHandlerTuple(None, None)}
    with pytest.raises(ImproperlyConfiguredException) as exc:
        validate_node(node)
    assert "unique path" in str(exc.value)


def test_validate_node_valid_mount_no_children() -> None:
    node = create_node()
    node.is_mount = True
    validate_node(node)


def test_validate_node_valid_mount_static_children() -> None:
    child = create_node()
    node = create_node()
    node.is_mount = True
    node.children = {"static": child}
    validate_node(node)


def test_validate_node_invalid_mount_with_param_child() -> None:
    param = PathParameterDefinition("id", "str", "id:int", int)
    child = create_node()
    child.path_parameters = {"GET": (param,)}
    node = create_node()
    node.is_mount = True
    node.children = {"param_child": child}
    with pytest.raises(ImproperlyConfiguredException) as exc:
        validate_node(node)
    assert "Path parameters are not allowed under a static or mount route" in str(exc.value)


def test_validate_node_recursive_child_error() -> None:
    param = PathParameterDefinition("id", "int", "id:int", int)
    grandchild = create_node()
    grandchild.path_parameters = {"GET": (param,)}
    child = create_node()
    child.is_mount = True
    child.children = {"gc": grandchild}
    node = create_node()
    node.children = {"c": child}

    with pytest.raises(ImproperlyConfiguredException) as exc:
        validate_node(node)
    assert "Path parameters are not allowed" in str(exc.value)


def test_validate_node_complex_valid_tree() -> None:
    grandchild = create_node()
    grandchild.path_parameters = {}
    child1 = create_node()
    child1.is_mount = True
    child1.children = {"gc": grandchild}
    child2 = create_node()
    child2.is_asgi = True
    child2.asgi_handlers = {"asgi": ASGIHandlerTuple(None, None)}

    node = create_node()
    node.children = {"c1": child1, "c2": child2}
    validate_node(node)


def test_validate_node_asgi_with_websocket() -> None:
    node = create_node()
    node.is_asgi = True
    node.asgi_handlers = {
        "asgi": ASGIHandlerTuple(None, None),
        "websocket": ASGIHandlerTuple(None, None),
    }
    with pytest.raises(ImproperlyConfiguredException):
        validate_node(node)
