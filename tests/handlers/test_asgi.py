from speedy import ScopeType, MediaType
from speedy.handlers import asgi
from speedy.response.base import ASGIResponse
from speedy.status_code import HTTP_200_OK
from speedy.testing import create_test_client
from speedy.types import Scope, Receive, Send


def test_handle_asgi() -> None:
    @asgi(path="/")
    async def root_asgi_handler(scope: Scope, receive: Receive, send: Send) -> None:
        assert scope["type"] == ScopeType.HTTP
        assert scope["method"] == "GET"
        response = ASGIResponse(body=b"Hello World", media_type=MediaType.TEXT)
        await response(scope, receive, send)

    with create_test_client([root_asgi_handler]) as client:
        response = client.get("/")
        assert response.status_code == HTTP_200_OK
        assert response.text == "Hello World"
