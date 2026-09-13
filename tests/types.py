from typing import TYPE_CHECKING, Protocol

import httpx2

from speedy.testclient import TestClient
from speedy.types import ASGIApplication

if TYPE_CHECKING:

    class TestClientFactory(Protocol):
        def __call__(
                self,
                app: ASGIApplication,
                base_url: str = "http://testserver",
                raise_server_exceptions: bool = True,
                root_path: str = "",
                cookies: httpx2._types.CookieTypes | None = None,
                headers: dict[str, str] | None = None,
                follow_redirects: bool = True,
                client: tuple[str, int] = ("testclient", 50000),
        ) -> TestClient: ...
else:

    class TestClientFactory:
        __test__ = False
