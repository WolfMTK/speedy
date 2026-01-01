import re
from typing import Iterable


def normalize_path(path: str) -> str:
    """ Normalizes the given path string. """
    path = path.strip("/")
    path = f"/{path}"
    return re.compile("//+").sub("/", path)


def join_paths(paths: Iterable[str]) -> str:
    """ Normalize and joins path fragments. """
    return normalize_path("/".join(paths))
