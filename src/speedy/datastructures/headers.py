import re
from abc import abstractmethod, ABC
from collections.abc import Mapping, Iterator
from dataclasses import dataclass, field
from typing import Any, ClassVar

from speedy._multipart import parse_content_header
from speedy.exceptions.http_exceptions import ImproperlyConfiguredException
from speedy.types import RawHeaders, Scope

ETAG_RE = re.compile(r"([Ww]/)?\"(.+)\"")
PRINTABLE_ASCII_RE: re.Pattern[str] = re.compile(r"^[ -~]+$")


class Headers(Mapping[str, str]):
    def __init__(
            self,
            headers: Mapping[str, str] | None = None,
            raw: RawHeaders | None = None,
            scope: Scope | None = None,
    ) -> None:
        self._raw: RawHeaders = self._get_raw(headers, raw, scope)

    def __getitem__(self, item: str) -> str:
        header_key = item.lower().encode("latin-1")
        for key, value in self._raw:
            if header_key == key:
                return value.decode("latin-1")
        raise KeyError(item)

    def __contains__(self, item: Any) -> bool:
        header_key = item.lower().encode("latin-1")
        for key, _ in self._raw:
            if header_key == key:
                return True
        return False

    def __iter__(self) -> Iterator[Any]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self._raw)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Headers):
            return False
        return sorted(self._raw) == sorted(other._raw)

    def __repr__(self) -> str:
        name = type(self).__name__
        as_dict = dict(self.items())
        if len(as_dict) == len(self):
            return f"{name}({as_dict!r})"
        return f"{name}(raw={self.raw!r})"

    @property
    def raw(self) -> RawHeaders:
        """ Get RawHeaders. """
        return self._raw.copy()

    @classmethod
    def from_scope(cls, scope: Scope) -> "Headers":
        """ Create headers from a send-message. """
        headers = cls(scope=scope)
        return headers

    def keys(self) -> list[str]:
        """ Get keys. """
        return [key.decode("latin-1") for key, _ in self._raw]

    def values(self) -> list[str]:
        """ Get values. """
        return [value.decode("latin-1") for key, value in self._raw]

    def items(self) -> list[tuple[str, str]]:
        """ Get items. """
        return [(
            key.decode("latin-1"),
            value.decode("latin-1"),
        ) for key, value in self._raw]

    def getlist(self, key: str) -> list[str]:
        """ Get list values. """
        header_key = key.lower().encode("latin-1")
        return [value.decode("latin-1") for key, value in self._raw if
                header_key == key]

    def mutablecopy(self) -> "MutableHeaders":
        return MutableHeaders(raw=self.raw)

    def _get_raw(self,
                 headers: Mapping[str, str] | None = None,
                 raw: RawHeaders | None = None,
                 scope: Scope | None = None,
                 ) -> RawHeaders:
        if headers is not None:
            if raw is not None:
                raise AttributeError("Cannot set both \"headers\" and \"raw\".")

            if scope is not None:
                raise AttributeError("Cannot set both \"headers\" and \"scope\".")

            return [(
                key.lower().encode("latin-1"),
                value.encode("latin-1"),
            ) for key, value in headers.items()]
        elif raw is not None:
            if scope is not None:
                raise AttributeError("Cannot set both \"raw\" and \"scope\".")
            return raw
        elif scope is not None:
            return list(scope["headers"])
        return []


class MutableHeaders(Headers):
    def __setitem__(self, key: str, value: str) -> None:
        key = key.lower().encode("latin-1")
        value = value.encode("latin-1")

        updated_index = None
        removed_indexes = []
        for index, (_key, _) in enumerate(self._raw):
            if key == _key:
                if updated_index is None:
                    updated_index = index
                    continue
                removed_indexes.append(index)

        if updated_index is not None:
            self._raw[updated_index] = (key, value)
        else:
            self._raw.append((key, value))

        for index in removed_indexes:
            del self._raw[index]

    def __delitem__(self, key: str) -> None:
        key = key.lower().encode("latin-1")

        indexes = []
        for index, (_key, _) in enumerate(self._raw):
            if key == _key:
                indexes.append(index)

        for index in indexes:
            del self._raw[index]

    def __ior__(self, other: Mapping[str, str]) -> "MutableHeaders":
        if not isinstance(other, Mapping):
            raise TypeError(
                f"Expected a mapping but got {type(other).__name__}",
            )
        self.update(other)
        return self

    def __or__(self, other: Mapping[str, str]) -> "MutableHeaders":
        if not isinstance(other, Mapping):
            raise TypeError(
                f"Expected a mapping but got {type(other).__name__}",
            )
        mutable_headers = self.mutablecopy()
        mutable_headers.update(other)
        return mutable_headers

    @property
    def raw(self) -> RawHeaders:
        """ Get RawHeaders. """
        return self._raw

    def update(self, other: Mapping[str, str]) -> None:
        """ Update RawHeaders. """
        for key, val in other.items():
            self[key] = val

    def append(self, key: str, value: str) -> None:
        """ Append a header, preserving any duplicate entries. """
        self._raw.append(
            (key.lower().encode("latin-1"), value.encode("latin-1")),
        )

    def setdefault(self, key: str, value: str) -> str:
        """ Set default key and value in RawHeaders. """
        key_header = key.lower().encode("latin-1")
        value_header = value.encode("latin-1")

        for index, (_key, _value) in enumerate(self._raw):
            if key_header == _key:
                return _value.decode("latin-1")
        self._raw.append((key_header, value_header))
        return value

    def add_vary_header(self, vary: str) -> None:
        """ Extend a multivalued header. """
        existing = self.get("vary")
        if existing is not None:
            vary = ", ".join([existing, vary])
        self["vary"] = vary


@dataclass
class Header(ABC):
    """An abstract type for HTTP headers."""

    HEADER_NAME: ClassVar[str] = ""

    @abstractmethod
    def _get_header_value(self) -> str:
        """ Get the header value as string. """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_header(cls, header_value: str) -> "Header":
        """Construct a header from its string representation."""

    def to_header(self, include_header_name: bool = False) -> str:
        """ Get the header as string. """

        if not self.HEADER_NAME:
            raise ImproperlyConfiguredException("Missing header name")

        return (f"{self.HEADER_NAME}: " if include_header_name else "") + self._get_header_value()


@dataclass
class ETag(Header):
    """ An ``etag`` header. """

    HEADER_NAME: ClassVar[str] = "etag"

    weak: bool = field(default=False)
    value: str | None = field(default=None)

    @classmethod
    def from_header(cls, header_value: str) -> "ETag":
        """ Construct an ``etag`` header from its string representation. """
        match = ETAG_RE.match(header_value)
        if not match:
            raise ImproperlyConfiguredException
        weak, value = match.group(1, 2)
        try:
            return cls(weak=bool(weak), value=value)
        except ValueError as exc:
            raise ImproperlyConfiguredException from exc

    def _get_header_value(self) -> str:
        value = f"\"{self.value}\""
        return f"W/{value}" if self.weak else value


class MediaTypeHeader:
    """ A helper class for `Accept` header parsing. """

    def __init__(self, type_str: str) -> None:
        self._params_str = "".join(type_str.partition(";")[1:])

        full_type, self.params = parse_content_header(type_str)
        self.maintype, _, self.subtype = full_type.partition("/")

    def __str__(self) -> str:
        return f"{self.maintype}/{self.subtype}{self._params_str}"

    def copy(self) -> "MediaTypeHeader":
        """ Creates a shallow copy of the `MediaTypeHeader` instance. """
        new_obj = self.__class__.__new__(self.__class__)
        new_obj._params_str = self._params_str
        new_obj.params = self.params
        new_obj.maintype = self.maintype
        new_obj.subtype = self.subtype
        return new_obj

    @property
    def priority(self) -> tuple[int, int]:
        """ Calculates and returns the priority tuple for this media type. """
        quality = 100
        q_value_str = self.params.get("q")
        if q_value_str is not None:
            try:
                quality = int(100 * max(0.0, min(1.0, float(q_value_str))))
            except (ValueError, TypeError):
                pass

        if self.maintype == "*":
            specificity = 0
        elif self.subtype == "*":
            specificity = 1
        elif sum(1 for k in self.params if k != "q") == 0:
            specificity = 2
        else:
            specificity = 3
        return quality, specificity

    def match(self, other: "MediaTypeHeader") -> bool:
        """ Checks if this `MediaTypeHeader` matches another based on HTTP `Accept` header rules. """
        params_match = all(
            other.params.get(key) == value
            for key, value in self.params.items()
            if key != "q"
        )
        if not params_match:
            return False
        types_match = (
                self.maintype == "*" or
                other.maintype == "*" or
                self.maintype == other.maintype
        )
        if not types_match:
            return False
        return (
                self.subtype == "*" or
                other.subtype == "*" or
                self.subtype == other.subtype
        )


class Accept:
    """ An ``accept`` header. """

    def __init__(self, value: str) -> None:
        self._accepted_types = sorted(
            (MediaTypeHeader(val) for val in value.split(",")),
            key=lambda x: x.priority,
            reverse=True,
        )

    def __len__(self) -> int:
        return len(self._accepted_types)

    def __getitem__(self, index: int) -> str:
        return str(self._accepted_types[index])

    def __iter__(self) -> Iterator[str]:
        return map(str, self._accepted_types)

    def best_match(self, provided_types: list[str], default: str | None = None) -> str | None:
        """ Find the best matching media type for the request. """
        types = set(MediaTypeHeader(val) for val in provided_types)

        for accepted in self._accepted_types:
            for provided in types:
                if provided.match(accepted):
                    result = provided.copy()
                    if result.subtype == "*":
                        result.subtype = accepted.subtype
                    if result.maintype == "*":
                        result.maintype = accepted.maintype
                    return str(result)
        return default

    def accepts(self, media_type: str) -> bool:
        """ Check if the request accepts the specified media type. """
        return self.best_match([media_type]) == media_type
