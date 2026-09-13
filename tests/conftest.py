import functools
from typing import Literal, Any

import pytest
from speedy.testclient import TestClient
from tests.types import TestClientFactory


@pytest.fixture
def test_client_factory(
        anyio_backend_name: Literal["asyncio", "trio"],
        anyio_backend_options: dict[str, Any],
) -> TestClientFactory:
    return functools.partial(
        TestClient,
        backend=anyio_backend_name,
        backend_options=anyio_backend_options,
    )
