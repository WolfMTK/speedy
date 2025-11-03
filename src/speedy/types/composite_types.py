from collections.abc import Mapping, Callable
from typing import TypeAlias, Sequence, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from speedy.datastructures import Cookie, ResponseHeader
    from speedy.params import ParameterKwarg
    from speedy.types.asgi_types import ASGIApplication

ResponseHeaders: TypeAlias = "Sequence[ResponseHeader] | Mapping[str, str]"

ResponseCookies: TypeAlias = "Sequence[Cookie] | Mapping[str, str]"

TypeEncodersMap: TypeAlias = Mapping[Any, Callable[[Any], Any]]

TypeDecodersSequence: TypeAlias = Sequence[tuple[Callable[[Any], bool], Callable[[Any, Any], Any]]]

Middleware: TypeAlias = Callable[..., "ASGIApplication"]

ParametersMap: TypeAlias = "Mapping[str, ParameterKwarg]"
