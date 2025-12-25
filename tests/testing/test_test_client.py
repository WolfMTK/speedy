import pytest

from speedy.testing import create_test_client, create_async_test_client
from speedy.types import AnyIOBackend


@pytest.mark.parametrize("anyio_backend", ["asyncio", "trio"])
def test_test_client_get_set_session_data_no_backend(anyio_backend: "AnyIOBackend"):
    with create_test_client(backend=anyio_backend) as client:
        with pytest.raises(RuntimeError, match="Session backend not configured") as err:
            client.set_session_data({})

        with pytest.raises(RuntimeError, match="Session backend not configured"):
            client.get_session_data()


async def test_test_client_get_set_session_data_no_backend_async() -> None:
    async with create_async_test_client() as client:
        with pytest.raises(RuntimeError, match="Session backend not configured") as err:
           await client.set_session_data({})

        with pytest.raises(RuntimeError, match="Session backend not configured"):
            await client.get_session_data()
