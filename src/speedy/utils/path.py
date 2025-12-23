import re


def normalize_path(path: str) -> str:
    """ Normalizes the given path string. """
    path = path.strip("/")
    path = f"/{path}"
    return re.compile("//+").sub("/", path)
