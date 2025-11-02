import pytest

from speedy.utils.path import normalize_path


@pytest.mark.parametrize(
    "base, expected",
    [
        ("", "/"),
        ("/path", "/path"),
        ("path/", "/path"),
        ("path", "/path"),
        ("path////path", "/path/path"),
        ("path//", "/path"),
        ("///", "/"),
    ],
)
def test_normalize_path(base: str, expected: str) -> None:
    assert normalize_path(base) == expected
