from http import HTTPStatus
from typing import Any, Callable
from unittest.mock import MagicMock

import pytest

from speedy import Speedy
from speedy.connection import Request
from speedy.exceptions import HTTPException
from speedy.exceptions.base import SpeedyException
from speedy.middleware._internal.exceptions.middleware import ExceptionHandlerMiddleware
from speedy.status_code import HTTP_500_INTERNAL_SERVER_ERROR, HTTP_200_OK
from speedy.types import HTTPScope, HTTPReceiveMessage, Message, Scope, Receive, Send
from speedy.utils.scope.state import ScopeState


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
        Request(scope=scope),
        HTTPException(detail="exception", extra={"key": "value"}),
    )
    exc_status_code = HTTP_500_INTERNAL_SERVER_ERROR
    assert response.status_code == exc_status_code
    assert response.content == {
        "detail": HTTPStatus(exc_status_code).phrase,
        "extra": {"key": "value"},
        "status_code": exc_status_code,
    }


def test_default_handle_http_exception_handling_extra_none(
        scope: HTTPScope,
        middleware: ExceptionHandlerMiddleware,
) -> None:
    response = middleware.default_http_exception_handler(
        Request(scope=scope),
        HTTPException(detail="exception"),
    )
    exc_status_code = HTTP_500_INTERNAL_SERVER_ERROR
    assert response.status_code == exc_status_code
    assert response.content == {
        "detail": HTTPStatus(exc_status_code).phrase,
        "status_code": exc_status_code,
    }


def test_default_handle_http_exception_extra_list(
        scope: HTTPScope,
        middleware: ExceptionHandlerMiddleware,
) -> None:
    response = middleware.default_http_exception_handler(
        Request(scope=scope),
        HTTPException(
            detail="exception",
            extra=["key-1", "key-2"]
        ),
    )
    exc_status_code = HTTP_500_INTERNAL_SERVER_ERROR
    assert response.status_code == exc_status_code
    assert response.content == {
        "detail": HTTPStatus(exc_status_code).phrase,
        "extra": ["key-1", "key-2"],
        "status_code": exc_status_code,
    }


def test_default_handle_python_http_exception_handling(
        scope: HTTPScope,
        middleware: ExceptionHandlerMiddleware,
) -> None:
    response = middleware.default_http_exception_handler(
        Request(scope=scope),
        AttributeError("none"),
    )
    exc_status_code = HTTP_500_INTERNAL_SERVER_ERROR
    assert response.status_code == exc_status_code
    assert response.content == {
        "detail": HTTPStatus(exc_status_code).phrase,
        "status_code": exc_status_code,
    }
