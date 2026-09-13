from speedy.application import Speedy
from speedy.requests import Request
from speedy.responses import JSONResponse
from speedy.routing import Route
from speedy.testclient import TestClient
from tests.types import TestClientFactory


def mock_service_endpoint(request: Request) -> JSONResponse:
    return JSONResponse({"mock": "example"})


mock_service = Speedy(routes=[Route("/", endpoint=mock_service_endpoint)])


def test_use_testclient_in_endpoint(test_client_factory: TestClientFactory) -> None:
    def homepage(request: Request) -> JSONResponse:
        client = test_client_factory(mock_service)
        response = client.get("/")
        return JSONResponse(response.json())

    app = Speedy(routes=[Route("/", endpoint=homepage)])

    client = test_client_factory(app)
    response = client.get("/")
    assert response.json() == {"mock": "example"}


def test_testclient_headers_behavior() -> None:
    client = TestClient(mock_service)
    assert client.headers.get("user-agent") == "testclient"

    client = TestClient(mock_service, headers={"user-agent": "non-default-agent"})
    assert client.headers.get("user-agent") == "non-default-agent"

    client = TestClient(mock_service, headers={"Authentication": "Bearer 123"})
    assert client.headers.get("user-agent") == "testclient"
    assert client.headers.get("Authentication") == "Bearer 123"
