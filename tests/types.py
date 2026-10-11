from typing import TYPE_CHECKING, Protocol

from speedy.testclient import CookieTypes, TestClient
from speedy.types import ASGIApplication

if TYPE_CHECKING:

    class TestClientFactory(Protocol):
        def __call__(
                self,
                app: ASGIApplication,
                base_url: str = "http://testserver",
                raise_server_exceptions: bool = True,
                root_path: str = "",
                cookies: CookieTypes | None = None,
                headers: dict[str, str] | None = None,
                follow_redirects: bool = True,
                client: tuple[str, int] = ("testclient", 50000),
        ) -> TestClient: ...
else:

    class TestClientFactory:
        __test__ = False
