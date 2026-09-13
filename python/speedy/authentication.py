import functools
import inspect
from collections.abc import Callable, Iterable, Sequence
from typing import Any
from urllib.parse import urlencode

from speedy._speedy import HTTPConnection
from speedy.concurrency import is_async_callable
from speedy.exceptions import HTTPException
from speedy.requests import Request
from speedy.responses import RedirectResponse
from speedy.status import HTTP_303_SEE_OTHER, HTTP_403_FORBIDDEN
from speedy.websocket import WebSocket


def has_required_scope(connection: HTTPConnection, scopes: Sequence[str]) -> bool:
    return set(scopes) <= connection.auth.scopes


def requires[**P](
    scopes: str | Sequence[str],
    status_code: int = HTTP_403_FORBIDDEN,
    redirect: str | None = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    scopes_list = [scopes] if isinstance(scopes, str) else list(scopes)

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        sig = inspect.signature(func)
        for idx, parameter in enumerate(sig.parameters.values()):  # noqa: B007
            if parameter.name in {"request", "websocket"}:
                param_kind = parameter.name
                break
        else:
            raise TypeError(f'No "request" or "websocket" argument on function "{func}"')

        if param_kind == "websocket":

            @functools.wraps(func)
            async def websocket_wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
                websocket = kwargs.get("websocket", args[idx] if idx < len(args) else None)
                if not isinstance(websocket, WebSocket):
                    raise TypeError(
                        "Parameter with name 'websocket' is required to be of type"
                        f" 'WebSocket', not '{type(websocket).__name__}'"
                    )

                if not has_required_scope(websocket, scopes_list):
                    await websocket.close()
                else:
                    await func(*args, **kwargs)

            return websocket_wrapper

        if is_async_callable(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                request = _extract_request(kwargs, args, idx)

                if not has_required_scope(request, scopes_list):
                    if redirect is not None:
                        return _redirect_response(request, redirect)
                    raise HTTPException(status_code=status_code)
                return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            request = _extract_request(kwargs, args, idx)

            if not has_required_scope(request, scopes_list):
                if redirect is not None:
                    return _redirect_response(request, redirect)
                raise HTTPException(status_code=status_code)
            return func(*args, **kwargs)

        return sync_wrapper

    return decorator


def _extract_request(kwargs: dict[str, Any], args: tuple[Any, ...], idx: int) -> Request:
    request = kwargs.get("request", args[idx] if idx < len(args) else None)
    if not isinstance(request, Request):
        raise TypeError(
            f"Parameter with name 'request' is required to be of type 'Request', not '{type(request).__name__}'"
        )
    return request


def _redirect_response(request: Request, redirect: str) -> RedirectResponse:
    orig_request_qparam = urlencode({"next": str(request.url)})
    next_url = f"{request.url_for(redirect)}?{orig_request_qparam}"
    return RedirectResponse(url=next_url, status_code=HTTP_303_SEE_OTHER)


class AuthenticationBackend:
    """Base class for pluggable authentication backends."""

    async def authenticate(self, conn: HTTPConnection) -> tuple["AuthCredentials", "BaseUser"] | None:
        raise NotImplementedError


class AuthCredentials:
    """The scopes granted to an authenticated connection."""

    def __init__(self, scopes: Iterable[str] | None = None) -> None:
        self.scopes = frozenset(scopes) if scopes is not None else frozenset()


class BaseUser:
    @property
    def is_authenticated(self) -> bool:
        raise NotImplementedError

    @property
    def display_name(self) -> str:
        raise NotImplementedError

    @property
    def identity(self) -> str:
        raise NotImplementedError


class SimpleUser(BaseUser):
    def __init__(self, username: str) -> None:
        self.username = username

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.username

    @property
    def identity(self) -> str:
        return self.username


class UnauthenticatedUser(BaseUser):
    @property
    def is_authenticated(self) -> bool:
        return False

    @property
    def display_name(self) -> str:
        return ""

    @property
    def identity(self) -> str:
        return ""
