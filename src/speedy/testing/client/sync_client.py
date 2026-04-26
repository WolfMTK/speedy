import contextlib
from types import TracebackType
from typing import Generic, TypeVar, Any, Self, Sequence, Mapping
from warnings import warn

import anyio.from_thread
from httpx import Client, USE_CLIENT_DEFAULT
from httpx._client import UseClientDefault
from httpx._types import CookieTypes, QueryParamTypes, AuthTypes, HeaderTypes

from speedy.middleware.session.base import BaseBackendConfig, BaseSessionBackend
from speedy.testing.client._base import _prepare_ws_connect_request, _get_session_data, _set_session_data
from speedy.testing.lifespan_handler import LifeSpanHandler
from speedy.testing.transport import SyncTestClientTransport, ConnectionUpgradeExceptionError
from speedy.testing.websocket_test_session import WebSocketTestSession
from speedy.types import ASGIApp, AnyIOBackend

T = TypeVar("T", bound=ASGIApp)


class TestClient(Client, Generic[T]):
    __test__ = False

    def __init__(
            self,
            app: T,
            base_url: str = "http://testserver.local",
            raise_server_exceptions: bool = True,
            root_path: str = "",
            timeout: float | None = None,
            cookies: CookieTypes | None = None,
            backend: AnyIOBackend = "asyncio",
            backend_options: dict[str, Any] | None = None,
            session_config: BaseBackendConfig | None = None,
    ) -> None:
        if "." not in base_url:
            warn(
                f"The base_url {base_url!r} might cause issues. Try adding a domain name such as .local "
                f"`{base_url}.local`",
                UserWarning,
                stacklevel=1,
            )
        self._session_backend: BaseSessionBackend | None = None
        if session_config:
            self._session_backend = session_config._backend_class(config=session_config)

        self.app = app
        self.exit_stack = contextlib.ExitStack()
        self.blocking_portal = self.exit_stack.enter_context(
            anyio.from_thread.start_blocking_portal(
                backend=backend,
                backend_options=backend_options,
                name="test_client",
            ),
        )

        super().__init__(
            base_url=base_url,
            headers={"user-agent": "testclient"},
            follow_redirects=True,
            cookies=cookies,
            transport=SyncTestClientTransport(
                client=self,
                raise_server_exceptions=raise_server_exceptions,
                root_path=root_path,
            ),
            timeout=timeout,
        )

    def __enter__(self) -> Self:
        self.exit_stack.enter_context(self.blocking_portal.wrap_async_context_manager(LifeSpanHandler(self.app)))
        return self

    def __exit__(
            self,
            exc_type: type[BaseException] | None = None,
            exc_val: BaseException | None = None,
            exc_tb: TracebackType | None = None,
    ) -> None:
        self.exit_stack.__exit__(exc_type, exc_val, exc_tb)
        super().__exit__(exc_type)

    def websocket_connect(
            self,
            url: str,
            subprotocols: Sequence[str] | None = None,
            params: QueryParamTypes | None = None,
            headers: HeaderTypes | None = None,
            cookies: CookieTypes | None = None,
            auth: AuthTypes | UseClientDefault = USE_CLIENT_DEFAULT,
            follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
            timeout: float | None = None,
            extensions: Mapping[str, Any] | None = None,
    ) -> WebSocketTestSession:
        """ Sends a GET request to establish a websocket connection. """
        try:
            self.send(
                _prepare_ws_connect_request(
                    client=self,
                    url=url,
                    subprotocols=subprotocols,
                    params=params,
                    headers=headers,
                    cookies=cookies,
                    extensions=extensions,
                    timeout=timeout,
                ),
                auth=auth,
                follow_redirects=follow_redirects,
            )
        except ConnectionUpgradeExceptionError as exc:
            return WebSocketTestSession(
                client=self,
                scope=exc.scope,
                portal=self.blocking_portal,
                connect_timeout=timeout,
            )
        raise RuntimeError("Expected WebSocket upgrade")

    def get_session_data(self) -> dict[str, Any]:
        """ Get session data. """
        return self.blocking_portal.call(_get_session_data, self)

    def set_session_data(self, data: dict[str, Any]) -> None:
        """ Set session data. """
        self.blocking_portal.call(_set_session_data, self, data)
