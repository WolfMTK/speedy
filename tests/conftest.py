import pytest
from speedy.testclient import TestClient
from tests.types import TestClientFactory


@pytest.fixture
def test_client_factory() -> TestClientFactory:
    return TestClient
