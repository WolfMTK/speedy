from .multi_dicts import MultiMixin

from multidict import CIMultiDictProxy


class Headers(CIMultiDictProxy[str], MultiMixin[str]):
    def __init__(self) -> None:
        ...
