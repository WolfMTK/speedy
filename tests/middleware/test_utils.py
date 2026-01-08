import re
from typing import Any

import pytest

from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.middleware._utils import build_exclude_path_pattern


def test_build_exclude_path_pattern_empty() -> None:
    result = build_exclude_path_pattern(exclude=None)
    assert result is None


@pytest.mark.parametrize(
    "exclude, path, should_match",
    [
        ("/health", "/health", True),
        ("/health", "/metrics", False),
        ("/api/v1", "/api/v1/users", True),
    ],
)
def test_build_exclude_path_pattern_string(
        exclude: str,
        path: str,
        should_match: bool,
) -> None:
    result = build_exclude_path_pattern(exclude=exclude)
    assert isinstance(result, re.Pattern)

    match = result.search(path)
    assert bool(match) == should_match


@pytest.mark.parametrize(
    "exclude, path, should_match",
    [
        (["/health", "/metrics"], "/health", True),
        (["/health", "/metrics"], "/metrics", True),
        (["/health", "/metrics"], "/users", False),
        (("/a", "/b"), "/a", True),
    ],
)
def test_build_exclude_path_pattern_iterable(
        exclude: Any,
        path: str,
        should_match: bool,
) -> None:
    result = build_exclude_path_pattern(exclude=exclude)
    assert isinstance(result, re.Pattern)

    match = result.search(path)
    assert bool(match) == should_match


@pytest.mark.parametrize(
    "exclude",
    [
        "[invalid(regex)",
        ["valid", "[invalid("],
        ("(unclosed", "/path"),
    ],
)
def test_build_exclude_path_pattern_invalid(exclude: Any) -> None:
    with pytest.raises(ImproperlyConfiguredException) as exc_info:
        build_exclude_path_pattern(exclude=exclude)

    assert "Unable to compile exclude patterns" in str(exc_info.value)
