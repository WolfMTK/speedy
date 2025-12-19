from collections.abc import Mapping, Callable
from typing import Literal
from typing import TypeAlias, Sequence, TYPE_CHECKING, Any, MutableMapping, Union

if TYPE_CHECKING:
    from speedy import ScopeType
    from speedy.datastructures import Cookie, ResponseHeader
    from speedy.params import ParameterKwarg
    from speedy.types.asgi_types import ASGIApplication
    from .callable_types import ExceptionHandler

ResponseHeaders: TypeAlias = "Sequence[ResponseHeader] | Mapping[str, str]"

ResponseCookies: TypeAlias = "Sequence[Cookie] | Mapping[str, str]"

TypeEncodersMap: TypeAlias = Mapping[Any, Callable[[Any], Any]]

TypeDecodersSequence: TypeAlias = Sequence[tuple[Callable[[Any], bool], Callable[[Any, Any], Any]]]

Middleware: TypeAlias = Callable[..., "ASGIApplication"]

ParametersMap: TypeAlias = "Mapping[str, ParameterKwarg]"

ExceptionHandlersMap: TypeAlias = "MutableMapping[Union[int, type[Exception]], ExceptionHandler]"

Scopes: TypeAlias = "set[Literal[ScopeType.HTTP, ScopeType.WEBSOCKET]]"
