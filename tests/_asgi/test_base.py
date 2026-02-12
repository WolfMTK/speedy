from __future__ import annotations

import re
from typing import Any
from unittest.mock import AsyncMock

import pytest

from speedy._asgi.base import (
    BaseRouter,
    TrieRouter,
    RegExpRouter,
    SmartRouter,
    RouteAnalysis,
    _TrieNode,
    _analyse_routes,
)
from speedy.types import PathParameterDefinition


def get_param(name: str, type_: type = str) -> PathParameterDefinition:
    return PathParameterDefinition(name=name, type=type_, full=f"{name}:{type_.__name__}", parser=None)


def get_app() -> AsyncMock:
    return AsyncMock(name="asgi_app")


def get_handler() -> AsyncMock:
    return AsyncMock(name="handler")


@pytest.fixture()
def trie() -> TrieRouter:
    return TrieRouter()


@pytest.fixture()
def regexp() -> RegExpRouter:
    return RegExpRouter()


@pytest.fixture()
def smart() -> SmartRouter:
    return SmartRouter()


def test_trie_static_route_match(trie: TrieRouter) -> None:
    app, handler = get_app(), get_handler()
    trie.add_route(
        path="/users",
        method="GET",
        path_components=["users"],
        asgi_app=app,
        handler=handler,
        is_dynamic=False,
    )
    result = trie.match("/users", method="GET")
    assert result is not None
    assert result[0] is app
    assert result[1] is handler
    assert result[2] == {}


def test_trie_static_route_no_match_wrong_method(trie: TrieRouter) -> None:
    trie.add_route(
        path="/users",
        method="GET",
        path_components=["users"],
        asgi_app=get_app(),
        handler=get_handler(),
    )
    assert trie.match("/users", method="POST") is None


def test_trie_static_route_no_match_wrong_path(trie: TrieRouter) -> None:
    trie.add_route(
        path="/users",
        method="GET",
        path_components=["users"],
        asgi_app=get_app(),
        handler=get_handler(),
    )
    assert trie.match("/posts", method="GET") is None


def test_trie_multiple_static_routes(trie: TrieRouter) -> None:
    app_a, handler_a = get_app(), get_handler()
    app_b, handler_b = get_app(), get_handler()

    trie.add_route("/users", "GET", ["users"], app_a, handler_a)
    trie.add_route("/posts", "GET", ["posts"], app_b, handler_b)

    res_a = trie.match("/users", "GET")
    res_b = trie.match("/posts", "GET")

    assert res_a is not None and res_a[0] is app_a
    assert res_b is not None and res_b[0] is app_b


def test_trie_nested_static_route(trie: TrieRouter) -> None:
    app, handler = get_app(), get_handler()
    trie.add_route("/api/v1/health", "GET", ["api", "v1", "health"], app, handler)

    assert trie.match("/api/v1/health", "GET") is not None
    assert trie.match("/api/v1", "GET") is None
    assert trie.match("/api/v1/health/extra", "GET") is None


def test_trie_same_path_different_methods(trie: TrieRouter) -> None:
    app_get, h_get = get_app(), get_handler()
    app_post, h_post = get_app(), get_handler()

    trie.add_route("/users", "GET", ["users"], app_get, h_get)
    trie.add_route("/users", "POST", ["users"], app_post, h_post)

    res_get = trie.match("/users", "GET")
    res_post = trie.match("/users", "POST")

    assert res_get is not None and res_get[0] is app_get
    assert res_post is not None and res_post[0] is app_post


def test_trie_param_route_match(trie: TrieRouter) -> None:
    app, handler = get_app(), get_handler()
    trie.add_route(
        path="/users/{id:int}",
        method="GET",
        path_components=["users", get_param("id", int)],
        asgi_app=app,
        handler=handler,
        is_dynamic=True,
    )
    result = trie.match("/users/42", method="GET")
    assert result is not None
    assert result[0] is app
    assert result[2] == {"id": "42"}


def test_trie_multiple_params(trie: TrieRouter) -> None:
    app, handler = get_app(), get_handler()
    trie.add_route(
        path="/users/{user_id:int}/posts/{post_id:int}",
        method="GET",
        path_components=["users", get_param("user_id", int), "posts", get_param("post_id", int)],
        asgi_app=app,
        handler=handler,
        is_dynamic=True,
    )
    result = trie.match("/users/5/posts/99", method="GET")
    assert result is not None
    assert result[2] == {"user_id": "5", "post_id": "99"}


def test_trie_param_route_no_match_missing_segment(trie: TrieRouter) -> None:
    trie.add_route(
        path="/users/{id:int}",
        method="GET",
        path_components=["users", get_param("id", int)],
        asgi_app=get_app(),
        handler=get_handler(),
        is_dynamic=True,
    )
    assert trie.match("/users", method="GET") is None


def test_trie_static_preferred_over_param(trie: TrieRouter) -> None:
    app_static, h_static = get_app(), get_handler()
    app_param, h_param = get_app(), get_handler()

    trie.add_route("/users/me", "GET", ["users", "me"], app_static, h_static)
    trie.add_route(
        "/users/{id:str}",
        "GET",
        ["users", get_param("id")],
        app_param,
        h_param,
        is_dynamic=True,
    )

    result = trie.match("/users/me", "GET")
    assert result is not None
    assert result[0] is app_static
    assert result[2] == {}

    result = trie.match("/users/123", "GET")
    assert result is not None
    assert result[0] is app_param
    assert result[2] == {"id": "123"}


def test_trie_websocket_route_method_none(trie: TrieRouter) -> None:
    app, handler = get_app(), get_handler()
    trie.add_route("/ws", "websocket", ["ws"], app, handler)

    result = trie.match("/ws", method=None)
    assert result is not None
    assert result[0] is app


def test_trie_asgi_route_matches_any_method(trie: TrieRouter) -> None:
    app, handler = get_app(), get_handler()
    trie.add_route("/asgi", "asgi", ["asgi"], app, handler)

    assert trie.match("/asgi", method="GET") is not None
    assert trie.match("/asgi", method=None) is not None


def test_trie_clear(trie: TrieRouter) -> None:
    trie.add_route("/a", "GET", ["a"], get_app(), get_handler())
    trie.add_route("/b", "GET", ["b"], get_app(), get_handler())
    assert len(trie) == 2

    trie.clear()
    assert len(trie) == 0
    assert trie.match("/a", "GET") is None


def test_trie_root_path(trie: TrieRouter) -> None:
    app, handler = get_app(), get_handler()
    trie.add_route("/", "GET", [], app, handler)

    result = trie.match("/", method="GET")
    assert result is not None
    assert result[0] is app


def test_trie_static_route_returns_path_as_template(trie: TrieRouter) -> None:
    trie.add_route("/health", "GET", ["health"], get_app(), get_handler())
    result = trie.match("/health", "GET")
    assert result is not None
    assert result[3] == "/health"


def test_trie_dynamic_route_preserves_path_template(trie: TrieRouter) -> None:
    trie.add_route(
        "/users/{id:int}",
        "GET",
        ["users", get_param("id", int)],
        get_app(),
        get_handler(),
        is_dynamic=True,
    )
    result = trie.match("/users/1", "GET")
    assert result is not None
    assert result[3] == "/users/{id:int}"


def test_regexp_static_route(regexp: RegExpRouter) -> None:
    app, handler = get_app(), get_handler()
    regexp.add_route("/users", "GET", ["users"], app, handler)

    result = regexp.match("/users", "GET")
    assert result is not None
    assert result[0] is app
    assert result[2] == {}


def test_regexp_static_no_match(regexp: RegExpRouter) -> None:
    regexp.add_route("/users", "GET", ["users"], get_app(), get_handler())
    assert regexp.match("/posts", "GET") is None


def test_regexp_static_wrong_method(regexp: RegExpRouter) -> None:
    regexp.add_route("/users", "GET", ["users"], get_app(), get_handler())
    assert regexp.match("/users", "POST") is None


def test_regexp_param_route(regexp: RegExpRouter) -> None:
    app, handler = get_app(), get_handler()
    regexp.add_route(
        "/users/{id:int}",
        "GET",
        ["users", get_param("id", int)],
        app,
        handler,
        is_dynamic=True,
    )
    result = regexp.match("/users/42", "GET")
    assert result is not None
    assert result[0] is app
    assert result[2] == {"id": "42"}


def test_regexp_multiple_params(regexp: RegExpRouter) -> None:
    app, handler = get_app(), get_handler()
    regexp.add_route(
        "/users/{uid:int}/posts/{pid:int}",
        "GET",
        ["users", get_param("uid", int), "posts", get_param("pid", int)],
        app,
        handler,
        is_dynamic=True,
    )
    result = regexp.match("/users/5/posts/99", "GET")
    assert result is not None
    assert result[2] == {"uid": "5", "pid": "99"}


def test_regexp_cannot_add_after_build(regexp: RegExpRouter) -> None:
    regexp.add_route("/a", "GET", ["a"], get_app(), get_handler())
    regexp.match("/a", "GET")

    with pytest.raises(RuntimeError):
        regexp.add_route("/b", "GET", ["b"], get_app(), get_handler())


def test_regexp_websocket_route(regexp: RegExpRouter) -> None:
    app, handler = get_app(), get_handler()
    regexp.add_route("/ws", "websocket", ["ws"], app, handler)

    result = regexp.match("/ws", method=None)
    assert result is not None
    assert result[0] is app


def test_regexp_asgi_fallback(regexp: RegExpRouter) -> None:
    app, handler = get_app(), get_handler()
    regexp.add_route("/catch", "asgi", ["catch"], app, handler)

    assert regexp.match("/catch", method="GET") is not None
    assert regexp.match("/catch", method=None) is not None


def test_regexp_clear_allows_rebuild(regexp: RegExpRouter) -> None:
    regexp.add_route("/a", "GET", ["a"], get_app(), get_handler())
    regexp.match("/a", "GET")

    regexp.clear()
    assert len(regexp) == 0

    regexp.add_route("/b", "GET", ["b"], get_app(), get_handler())
    result = regexp.match("/b", "GET")
    assert result is not None


def test_regexp_multiple_routes_same_method(regexp: RegExpRouter) -> None:
    app_a, h_a = get_app(), get_handler()
    app_b, h_b = get_app(), get_handler()

    regexp.add_route("/users", "GET", ["users"], app_a, h_a)
    regexp.add_route("/posts", "GET", ["posts"], app_b, h_b)

    res_a = regexp.match("/users", "GET")
    res_b = regexp.match("/posts", "GET")

    assert res_a is not None and res_a[0] is app_a
    assert res_b is not None and res_b[0] is app_b


def test_smart_selects_router_and_matches(smart: SmartRouter) -> None:
    app, handler = get_app(), get_handler()
    smart.add_route("/hello", "GET", ["hello"], app, handler)
    smart.construct()

    result = smart.match("/hello", "GET")
    assert result is not None
    assert result[0] is app


def test_smart_lazy_construct_on_first_match() -> None:
    smart = SmartRouter()
    app, handler = get_app(), get_handler()
    smart.add_route("/lazy", "GET", ["lazy"], app, handler)

    result = smart.match("/lazy", "GET")
    assert result is not None
    assert result[0] is app


def test_smart_no_match_returns_none(smart: SmartRouter) -> None:
    smart.add_route("/a", "GET", ["a"], get_app(), get_handler())
    smart.construct()
    assert smart.match("/nonexistent", "GET") is None


def test_smart_falls_back_when_preferred_router_rejects() -> None:
    class _AlwaysFailRouter(BaseRouter):
        name = "AlwaysFail"

        def add_route(self, *args: Any, **kwargs: Any) -> None:
            raise ValueError("I reject everything")

        def match(self, path: str, method: Any = None) -> None:
            return None

        def clear(self) -> None:
            pass

    trie = TrieRouter()
    smart = SmartRouter(routers=[_AlwaysFailRouter(), trie])

    app, handler = get_app(), get_handler()
    smart.add_route("/fallback", "GET", ["fallback"], app, handler)
    smart.construct()

    assert smart._active_router is trie
    result = smart.match("/fallback", "GET")
    assert result is not None
    assert result[0] is app


def test_smart_param_route_through_smart(smart: SmartRouter) -> None:
    app, handler = get_app(), get_handler()
    smart.add_route(
        "/items/{id:int}",
        "GET",
        ["items", get_param("id", int)],
        app,
        handler,
        is_dynamic=True,
    )
    smart.construct()

    result = smart.match("/items/7", "GET")
    assert result is not None
    assert result[2] == {"id": "7"}


def test_smart_clear_and_reconstruct(smart: SmartRouter) -> None:
    smart.add_route("/x", "GET", ["x"], get_app(), get_handler())
    smart.construct()
    assert smart.match("/x", "GET") is not None

    smart.clear()
    assert len(smart) == 0
    assert smart._active_router is None
    assert smart.analysis is None

    app2, h2 = get_app(), get_handler()
    smart.add_route("/y", "GET", ["y"], app2, h2)
    smart.construct()

    assert smart.match("/x", "GET") is None
    result = smart.match("/y", "GET")
    assert result is not None
    assert result[0] is app2


def test_smart_websocket_through_smart(smart: SmartRouter) -> None:
    app, handler = get_app(), get_handler()
    smart.add_route("/ws", "websocket", ["ws"], app, handler)
    smart.construct()

    result = smart.match("/ws", method=None)
    assert result is not None
    assert result[0] is app


def test_smart_len_tracks_pending(smart: SmartRouter) -> None:
    assert len(smart) == 0
    smart.add_route("/a", "GET", ["a"], get_app(), get_handler())
    smart.add_route("/b", "POST", ["b"], get_app(), get_handler())
    assert len(smart) == 2


def test_smart_all_fail_uses_last_fallback() -> None:
    class _FailOnce(BaseRouter):
        name = "FailOnce"
        _called = False

        def add_route(self, *args: Any, **kwargs: Any) -> None:
            if not self._called:
                self._called = True
                raise RuntimeError("fail")

        def match(self, path: str, method: Any = None) -> None:
            return None

        def clear(self) -> None:
            self._called = False

    trie = TrieRouter()
    smart = SmartRouter(routers=[_FailOnce(), trie])

    app, handler = get_app(), get_handler()
    smart.add_route("/ok", "GET", ["ok"], app, handler)
    smart.construct()

    assert smart._active_router is trie
    result = smart.match("/ok", "GET")
    assert result is not None


def test_analyse_routes_empty() -> None:
    analysis = _analyse_routes([])
    assert analysis.total == 0
    assert analysis.static_ratio == 0.0
    assert analysis.dynamic_ratio == 0.0


def test_analyse_routes_all_static() -> None:
    pending = [
        ("/a", "GET", ["a"], get_app(), get_handler(), False),
        ("/b", "POST", ["b"], get_app(), get_handler(), False),
        ("/c/d", "GET", ["c", "d"], get_app(), get_handler(), False),
    ]
    analysis = _analyse_routes(pending)
    assert analysis.total == 3
    assert analysis.static_count == 3
    assert analysis.dynamic_count == 0
    assert analysis.static_ratio == 1.0
    assert analysis.dynamic_ratio == 0.0
    assert analysis.max_depth == 2
    assert analysis.has_overlapping_params is False


def test_analyse_routes_all_dynamic() -> None:
    pending = [
        ("/users/{id:int}", "GET", ["users", get_param("id", int)],
         get_app(), get_handler(), True),
        ("/posts/{slug:str}", "GET", ["posts", get_param("slug")],
         get_app(), get_handler(), True),
    ]
    analysis = _analyse_routes(pending)
    assert analysis.total == 2
    assert analysis.static_count == 0
    assert analysis.dynamic_count == 2
    assert analysis.dynamic_ratio == 1.0
    assert analysis.max_params_per_route == 1


def test_analyse_routes_mixed() -> None:
    pending = [
        ("/health", "GET", ["health"], get_app(), get_handler(), False),
        ("/users/{id:int}", "GET", ["users", get_param("id", int)],
         get_app(), get_handler(), True),
    ]
    analysis = _analyse_routes(pending)
    assert analysis.total == 2
    assert analysis.static_count == 1
    assert analysis.dynamic_count == 1
    assert analysis.static_ratio == 0.5
    assert analysis.dynamic_ratio == 0.5


def test_analyse_routes_overlapping_params_detected() -> None:
    pending = [
        ("/users/{id:int}", "GET", ["users", get_param("id", int)],
         get_app(), get_handler(), True),
        ("/users/{slug:str}", "GET", ["users", get_param("slug")],
         get_app(), get_handler(), True),
    ]
    analysis = _analyse_routes(pending)
    assert analysis.has_overlapping_params is True


def test_analyse_routes_no_overlapping_when_same_param_name() -> None:
    pending = [
        ("/users/{id:int}", "GET", ["users", get_param("id", int)],
         get_app(), get_handler(), True),
        ("/users/{id:int}/posts", "GET",
         ["users", get_param("id", int), "posts"],
         get_app(), get_handler(), True),
    ]
    analysis = _analyse_routes(pending)
    assert analysis.has_overlapping_params is False


def test_analyse_routes_unique_methods_counted() -> None:
    pending = [
        ("/a", "GET", ["a"], get_app(), get_handler(), False),
        ("/a", "POST", ["a"], get_app(), get_handler(), False),
        ("/b", "GET", ["b"], get_app(), get_handler(), False),
    ]
    analysis = _analyse_routes(pending)
    assert analysis.unique_methods == 2


def test_analyse_routes_max_depth_tracked() -> None:
    pending = [
        ("/a", "GET", ["a"], get_app(), get_handler(), False),
        ("/a/b/c/d/e", "GET", ["a", "b", "c", "d", "e"],
         get_app(), get_handler(), False),
    ]
    analysis = _analyse_routes(pending)
    assert analysis.max_depth == 5


def test_analyse_routes_max_params_per_route() -> None:
    pending = [
        ("/u/{a:int}/p/{b:int}/c/{c:int}", "GET",
         ["u", get_param("a", int), "p", get_param("b", int), "c", get_param("c", int)],
         get_app(), get_handler(), True),
    ]
    analysis = _analyse_routes(pending)
    assert analysis.max_params_per_route == 3


def test_smart_selection_all_static_selects_regexp() -> None:
    smart = SmartRouter()
    for i in range(10):
        smart.add_route(f"/route{i}", "GET", [f"route{i}"], get_app(), get_handler())
    smart.construct()

    assert smart.analysis is not None
    assert smart.analysis.static_ratio == 1.0
    assert smart._active_router is not None


def test_smart_selection_mostly_static_selects_regexp() -> None:
    smart = SmartRouter()
    for i in range(8):
        smart.add_route(f"/s{i}", "GET", [f"s{i}"], get_app(), get_handler())
    for i in range(2):
        smart.add_route(
            f"/d{i}/{{id:int}}", "GET",
            [f"d{i}", get_param("id", int)],
            get_app(), get_handler(), is_dynamic=True,
        )
    smart.construct()

    assert smart.analysis is not None
    assert smart.analysis.dynamic_ratio <= 0.30


def test_smart_selection_mostly_dynamic_selects_trie() -> None:
    smart = SmartRouter()
    smart.add_route("/health", "GET", ["health"], get_app(), get_handler())
    for i in range(9):
        smart.add_route(
            f"/resource{i}/{{id:int}}", "GET",
            [f"resource{i}", get_param("id", int)],
            get_app(), get_handler(), is_dynamic=True,
        )
    smart.construct()

    assert smart.analysis is not None
    assert smart.analysis.dynamic_ratio > 0.70


def test_smart_selection_overlapping_params_selects_trie() -> None:
    smart = SmartRouter()
    smart.add_route(
        "/items/{id:int}", "GET",
        ["items", get_param("id", int)],
        get_app(), get_handler(), is_dynamic=True,
    )
    smart.add_route(
        "/items/{slug:str}", "POST",
        ["items", get_param("slug")],
        get_app(), get_handler(), is_dynamic=True,
    )
    smart.construct()

    assert smart.analysis is not None
    assert smart.analysis.has_overlapping_params is True


def test_smart_selection_balanced_mix_selects_trie() -> None:
    smart = SmartRouter()
    for i in range(5):
        smart.add_route(f"/s{i}", "GET", [f"s{i}"], get_app(), get_handler())
    for i in range(5):
        smart.add_route(
            f"/d{i}/{{id:int}}", "GET",
            [f"d{i}", get_param("id", int)],
            get_app(), get_handler(), is_dynamic=True,
        )
    smart.construct()

    assert smart.analysis is not None


def test_smart_analysis_available_after_construct() -> None:
    smart = SmartRouter()
    assert smart.analysis is None

    smart.add_route("/x", "GET", ["x"], get_app(), get_handler())
    smart.construct()

    assert smart.analysis is not None
    assert smart.analysis.total == 1


def test_smart_analysis_cleared_on_clear() -> None:
    smart = SmartRouter()
    smart.add_route("/x", "GET", ["x"], get_app(), get_handler())
    smart.construct()
    assert smart.analysis is not None

    smart.clear()
    assert smart.analysis is None


def test_trie_node_initial_state() -> None:
    node = _TrieNode()
    assert node.children == {}
    assert node.param_child is None
    assert node.param_definition is None
    assert node.handlers == {}


def test_trie_node_children_isolation() -> None:
    a, b = _TrieNode(), _TrieNode()
    a.children["x"] = _TrieNode()
    assert "x" not in b.children


@pytest.mark.parametrize("router_cls", [TrieRouter, RegExpRouter])
def test_trailing_slash_treated_as_different(router_cls: type[BaseRouter]) -> None:
    router = router_cls()
    app_a, h_a = get_app(), get_handler()
    app_b, h_b = get_app(), get_handler()

    router.add_route("/users", "GET", ["users"], app_a, h_a)
    result = router.match("/users", "GET")
    assert result is not None


@pytest.mark.parametrize("router_cls", [TrieRouter, RegExpRouter])
def test_deeply_nested_path(router_cls: type[BaseRouter]) -> None:
    router = router_cls()
    components = ["a", "b", "c", "d", "e", "f"]
    path = "/" + "/".join(components)
    app, handler = get_app(), get_handler()

    router.add_route(path, "GET", components, app, handler)
    result = router.match(path, "GET")
    assert result is not None
    assert result[0] is app


def test_smart_router_with_mixed_routes() -> None:
    smart = SmartRouter()
    app_s, h_s = get_app(), get_handler()
    app_d, h_d = get_app(), get_handler()

    smart.add_route("/health", "GET", ["health"], app_s, h_s)
    smart.add_route(
        "/users/{id:int}",
        "GET",
        ["users", get_param("id", int)],
        app_d,
        h_d,
        is_dynamic=True,
    )
    smart.construct()

    res_static = smart.match("/health", "GET")
    assert res_static is not None and res_static[0] is app_s

    res_dynamic = smart.match("/users/42", "GET")
    assert res_dynamic is not None and res_dynamic[0] is app_d
    assert res_dynamic[2] == {"id": "42"}


def test_smart_router_many_routes() -> None:
    smart = SmartRouter()
    apps = {}
    for i in range(100):
        app, handler = get_app(), get_handler()
        path = f"/route{i}"
        smart.add_route(path, "GET", [f"route{i}"], app, handler)
        apps[path] = app

    smart.construct()

    for path, expected_app in apps.items():
        result = smart.match(path, "GET")
        assert result is not None
        assert result[0] is expected_app


@pytest.mark.parametrize("router_cls", [TrieRouter, RegExpRouter])
def test_static_path_template_preserved(router_cls: type[BaseRouter]) -> None:
    router = router_cls()
    router.add_route("/health", "GET", ["health"], get_app(), get_handler())
    result = router.match("/health", "GET")
    assert result is not None
    assert result[3] == "/health"


@pytest.mark.parametrize("router_cls", [TrieRouter, RegExpRouter])
def test_dynamic_path_template_preserved(router_cls: type[BaseRouter]) -> None:
    router = router_cls()
    router.add_route(
        "/users/{id:int}", "GET",
        ["users", get_param("id", int)],
        get_app(), get_handler(),
        is_dynamic=True,
    )
    result = router.match("/users/42", "GET")
    assert result is not None
    assert result[3] == "/users/{id:int}"


def test_path_template_through_smart_router() -> None:
    smart = SmartRouter()
    smart.add_route(
        "/items/{slug:str}", "GET",
        ["items", get_param("slug")],
        get_app(), get_handler(),
        is_dynamic=True,
    )
    smart.construct()
    result = smart.match("/items/hello-world", "GET")
    assert result is not None
    assert result[3] == "/items/{slug:str}"


@pytest.mark.parametrize("router_cls", [TrieRouter, RegExpRouter])
def test_root_path_match(router_cls: type[BaseRouter]) -> None:
    router = router_cls()
    app, handler = get_app(), get_handler()
    router.add_route("/", "GET", [], app, handler)
    result = router.match("/", "GET")
    assert result is not None
    assert result[0] is app
    assert result[3] == "/"


def test_smart_router_unknown_candidates_uses_original_order() -> None:
    class _CustomRouter(BaseRouter):
        name = "Custom"
        _routes: list = []

        def add_route(self, *args: Any, **kwargs: Any) -> None:
            self._routes.append(args)

        def match(self, path: str, method: Any = None) -> None:
            return None

        def clear(self) -> None:
            self._routes.clear()

    c1, c2 = _CustomRouter(), _CustomRouter()
    smart = SmartRouter(routers=[c1, c2])
    smart.add_route("/x", "GET", ["x"], get_app(), get_handler())
    smart.construct()

    assert smart._active_router is c1


def test_regexp_build_returns_self(regexp: RegExpRouter) -> None:
    regexp.add_route("/a", "GET", ["a"], get_app(), get_handler())
    result = regexp.build()
    assert result is regexp


def test_regexp_build_then_match(regexp: RegExpRouter) -> None:
    app, handler = get_app(), get_handler()
    regexp.add_route("/x", "GET", ["x"], app, handler)
    regexp.build()

    result = regexp.match("/x", "GET")
    assert result is not None
    assert result[0] is app


def test_regexp_build_idempotent(regexp: RegExpRouter) -> None:
    regexp.add_route("/a", "GET", ["a"], get_app(), get_handler())
    regexp.build()
    regexp.build()
    assert regexp.match("/a", "GET") is not None


def test_regexp_add_after_explicit_build_raises(regexp: RegExpRouter) -> None:
    regexp.add_route("/a", "GET", ["a"], get_app(), get_handler())
    regexp.build()

    with pytest.raises(RuntimeError):
        regexp.add_route("/b", "GET", ["b"], get_app(), get_handler())


def test_regexp_build_with_no_routes(regexp: RegExpRouter) -> None:
    regexp.build()
    assert regexp.match("/anything", "GET") is None


def test_regexp_root_path(regexp: RegExpRouter) -> None:
    app, handler = get_app(), get_handler()
    regexp.add_route("/", "GET", [], app, handler)
    result = regexp.match("/", "GET")
    assert result is not None
    assert result[0] is app
    assert result[3] == "/"


def test_regexp_dynamic_path_template(regexp: RegExpRouter) -> None:
    regexp.add_route(
        "/users/{id:int}", "GET",
        ["users", get_param("id", int)],
        get_app(), get_handler(),
        is_dynamic=True,
    )
    result = regexp.match("/users/42", "GET")
    assert result is not None
    assert result[3] == "/users/{id:int}"


def test_smart_construct_triggers_build_on_regexp() -> None:
    smart = SmartRouter()
    smart.add_route("/a", "GET", ["a"], get_app(), get_handler())
    smart.construct()

    router = smart._active_router
    assert router is not None
    assert router._built is True


def test_smart_construct_with_build_error_falls_back() -> None:
    class _BuildFailRouter(BaseRouter):
        name = "BuildFail"

        def add_route(self, *args: Any, **kwargs: Any) -> None:
            pass

        def build(self) -> None:
            raise ValueError("Cannot compile")

        def match(self, path: str, method: Any = None) -> None:
            return None

        def clear(self) -> None:
            pass

    trie = TrieRouter()
    smart = SmartRouter(routers=[_BuildFailRouter(), trie])
    smart.add_route("/x", "GET", ["x"], get_app(), get_handler())
    smart.construct()

    assert smart._active_router is trie


def test_route_analysis_default_values() -> None:
    analysis = RouteAnalysis()
    assert analysis.total == 0
    assert analysis.static_count == 0
    assert analysis.dynamic_count == 0
    assert analysis.max_depth == 0
    assert analysis.max_params_per_route == 0
    assert analysis.unique_methods == 0
    assert analysis.has_overlapping_params is False


def test_route_analysis_frozen_immutability() -> None:
    analysis = RouteAnalysis(total=5)
    with pytest.raises(AttributeError):
        analysis.total = 10


def test_route_analysis_static_ratio_zero_total() -> None:
    analysis = RouteAnalysis(total=0, static_count=0)
    assert analysis.static_ratio == 0.0


def test_route_analysis_dynamic_ratio_zero_total() -> None:
    analysis = RouteAnalysis(total=0, dynamic_count=0)
    assert analysis.dynamic_ratio == 0.0


def test_route_analysis_ratios_computed_correctly() -> None:
    analysis = RouteAnalysis(total=10, static_count=7, dynamic_count=3)
    assert analysis.static_ratio == pytest.approx(0.7)
    assert analysis.dynamic_ratio == pytest.approx(0.3)


def test_route_entry_creation() -> None:
    from speedy._asgi.base import RouteEntry
    entry = RouteEntry(
        method="GET",
        path="/users/{id:int}",
        path_components=["users", get_param("id", int)],
        asgi_app=get_app(),
        handler=get_handler(),
        is_dynamic=True,
    )
    assert entry.method == "GET"
    assert entry.path == "/users/{id:int}"
    assert entry.is_dynamic is True
    assert len(entry.path_components) == 2


def test_compile_route_creation() -> None:
    from speedy._asgi.base import CompileRoute
    pattern = re.compile(r"^/users/(?P<id>[^/]+)$")
    route = CompileRoute(
        pattern=pattern,
        method="GET",
        asgi_app=get_app(),
        handler=get_handler(),
        path_template="/users/{id:int}",
    )
    assert route.path_template == "/users/{id:int}"
    assert route.param_names == []
    assert route.specificity == 0


def test_compile_route_with_params() -> None:
    from speedy._asgi.base import CompileRoute
    route = CompileRoute(
        pattern=re.compile(r".*"),
        method="POST",
        asgi_app=get_app(),
        handler=get_handler(),
        path_template="/items/{slug:str}",
        param_names=["slug"],
        specificity=2,
    )
    assert route.param_names == ["slug"]
    assert route.specificity == 2


def test_trie_asgi_dynamic_route_fallback() -> None:
    trie = TrieRouter()
    app, handler = get_app(), get_handler()
    trie.add_route(
        "/catch/{path:str}", "asgi",
        ["catch", get_param("path")],
        app, handler,
        is_dynamic=True,
    )
    result = trie.match("/catch/anything", "GET")
    assert result is not None
    assert result[0] is app
    assert result[2] == {"path": "anything"}


def test_trie_dynamic_route_not_in_static_map() -> None:
    trie = TrieRouter()
    trie.add_route(
        "/users/{id:int}", "GET",
        ["users", get_param("id", int)],
        get_app(), get_handler(),
        is_dynamic=True,
    )
    assert len(trie._static_map) == 0


def test_trie_root_via_trie_walk_not_static_map() -> None:
    trie = TrieRouter()
    app, handler = get_app(), get_handler()
    trie.add_route("/", "asgi", [], app, handler, is_dynamic=False)

    result = trie.match("/", "GET")
    assert result is not None
    assert result[0] is app

    result = trie.match("/", method=None)
    assert result is not None
    assert result[0] is app
