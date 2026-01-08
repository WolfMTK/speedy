import re
from typing import Final

from speedy.config.allowed_hosts import AllowedHostsConfig
from speedy.datastructures import URL, MutableHeaders
from speedy.middleware.base import BaseMiddleware
from speedy.response.base import ASGIResponse
from speedy.response.redirect import ASGIRedirectResponse
from speedy.status_code import HTTP_400_BAD_REQUEST
from speedy.types import ASGIAppType, Receive, Scope, Send

_INVALID_HOST_BODY: Final = b'{"message":"invalid host header"}'


class AllowedHostsMiddleware(BaseMiddleware):
    """Middleware ensuring the host of a request originated in a trusted host."""

    def __init__(self, app: ASGIAppType, config: AllowedHostsConfig) -> None:
        super().__init__(
            app=app,
            exclude=config.exclude,
            exclude_opt_key=config.exclude_opt_key,
            scopes=config.scopes,
        )

        self.allowed_hosts_regex: re.Pattern | None = None
        self.redirect_domains: re.Pattern | None = None

        allowed_patterns: str[str] = set()
        redirect_domains: set[str] = set()

        for host in config.allowed_hosts:
            if host == "*":
                return

            if host.startswith("*."):
                allowed_patterns.add(rf".*\.{host.replace('*.', '')}$")
            else:
                allowed_patterns.add(host)

            if config.www_redirect and host.startswith("www."):
                redirect_domains.add(host.replace("www.", ""))

        if allowed_patterns:
            self.allowed_hosts_regex = re.compile("|".join(sorted(allowed_patterns)))

        if redirect_domains:
            self.redirect_domains = re.compile("|".join(sorted(redirect_domains)))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.allowed_hosts_regex is None:
            await self.app(scope, receive, send)
            return
        headers = MutableHeaders(scope=scope)
        host = headers.get("host")
        if host is None:
            host = headers.get("x-forwarded-host", "")

        if not host:
            response = ASGIResponse(
                body=_INVALID_HOST_BODY,
                status_code=HTTP_400_BAD_REQUEST,
            )
            await response(scope, receive, send)
            return

        if ":" in host:
            host = host.split(":")[0]

        if self.allowed_hosts_regex.fullmatch(host):
            await self.app(scope, receive, send)
            return

        if self.redirect_domains is not None and self.redirect_domains.fullmatch(host):
            url = URL.from_scope(scope)
            redirect_url = url.replace(netloc=f"www.{url.netloc}")
            redirect_response = ASGIRedirectResponse(path=str(redirect_url))
            await redirect_response(scope, receive, send)
            return

        response = ASGIResponse(
            body=_INVALID_HOST_BODY,
            status_code=HTTP_400_BAD_REQUEST,
        )
        await response(scope, receive, send)
