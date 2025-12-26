from typing import Any, Callable

import pytest

from speedy import Speedy
from speedy.connection import Request
from speedy.exceptions import HTTPException
from speedy.middleware._internal.exceptions.middleware import ExceptionHandlerMiddleware
from speedy.status_code import HTTP_500_INTERNAL_SERVER_ERROR
from speedy.types import HTTPScope


async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
    return None


@pytest.fixture
def app() -> Speedy:
    return Speedy()


@pytest.fixture
def middleware() -> ExceptionHandlerMiddleware:
    return ExceptionHandlerMiddleware(dummy_app)


@pytest.fixture
def scope(create_scope: Callable[..., HTTPScope], app: Speedy) -> HTTPScope:
    return create_scope(app=app)

def test_default_handle_http_exception_handling_extra_object(
        scope: HTTPScope,
        middleware: ExceptionHandlerMiddleware,
) -> None:
    response = middleware.default_http_exception_handler(
        Request(scope=scope), HTTPException(detail="exception", extra={"key": "value"})
    )
    assert response.status_code == HTTP_500_INTERNAL_SERVER_ERROR
    assert response.content == {
        "detail": "Internal Server Error",
        "extra": {"key": "value"},
        "status_code": HTTP_500_INTERNAL_SERVER_ERROR,
    }

