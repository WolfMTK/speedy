from collections.abc import Mapping, Callable
from typing import TypeAlias, Sequence, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from speedy.datastructures import Cookie, ResponseHeader

ResponseHeaders: TypeAlias = "Sequence[ResponseHeader] | Mapping[str, str]"

ResponseCookies: TypeAlias = "Sequence[Cookie] | Mapping[str, str]"

TypeEncodersMap: TypeAlias = Mapping[Any, Callable[[Any], Any]]
