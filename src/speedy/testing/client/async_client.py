import contextlib
from types import TracebackType
from typing import Generic, TypeVar, Self, Sequence, Mapping, Any
from warnings import warn

import anyio
from httpx import AsyncClient, USE_CLIENT_DEFAULT
from httpx._client import UseClientDefault
from httpx._types import CookieTypes, QueryParamTypes, HeaderTypes, AuthTypes

from speedy.middleware.session.base import BaseBackendConfig, BaseSessionBackend
from speedy.testing.client._base import _prepare_ws_connect_request, _get_session_data, _set_session_data
from speedy.testing.lifespan_handler import LifeSpanHandler
from speedy.testing.transport import TestClientTransport, ConnectionUpgradeExceptionError
from speedy.testing.websocket_test_session import AsyncWebSocketTestSession
from speedy.types import ASGIAppType

T = TypeVar("T", bound=ASGIAppType)

class AsyncTestClient(AsyncClient, Generic[T]):
    def __init__(
            self,
            app: T,
            base_url: str = "http://testserver.local",
            raise_server_exceptions: bool = True,
            root_path: str = "",
            timeout: float | None = None,
            cookies: CookieTypes | None = None,
            session_config: BaseBackendConfig | None = None,
    ) -> None:
        if "." not in base_url:
            warn(
                f"The base_url {base_url!r} might cause issues. Try adding a domain name such as .local: "
                f"`{base_url}.local",
                UserWarning,
                stacklevel=1,
            )

        self.app = app

        self._session_backend: BaseSessionBackend | None = None
        if session_config:
            self._session_backend = session_config._backend_class(config=session_config)

        self.exit_stack = contextlib.AsyncExitStack()

        super().__init__(
            base_url=base_url,
            headers={"user-agent": "testclient"},
            follow_redirects=True,
            cookies=cookies,
            transport=TestClientTransport(
                client=self,
                raise_server_exceptions=raise_server_exceptions,
                root_path=root_path,
            ),
            timeout=timeout,
        )

    async def __aenter__(self) -> Self:
        self._tg = await self.exit_stack.enter_async_context(anyio.create_task_group())
        lifespan_handler = LifeSpanHandler(app=self.app)
        await self.exit_stack.enter_async_context(lifespan_handler)
        return self

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None = None,
            exc_val: BaseException | None = None,
            exc_tb: TracebackType | None = None,
    ) -> None:
        await self.exit_stack.__aexit__(exc_type, exc_val, exc_tb)
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def websocket_connect(
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
    ) -> AsyncWebSocketTestSession:
        """ Sends a GET request to establish a websocket connection. """
        try:
            await self.send(
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
            return AsyncWebSocketTestSession(
                app=self.app,
                scope=exc.scope,
                connect_timeout=timeout,
                tg=self._tg,
            )

        raise RuntimeError("Expected WebSocket upgrade")

    async def get_session_data(self) -> dict[str, Any]:
        """ Get session data. """
        return await _get_session_data(self)

    async def set_session_data(self, data: dict[str, Any]) -> None:
        """ Set session data. """
        await _set_session_data(self, data)
