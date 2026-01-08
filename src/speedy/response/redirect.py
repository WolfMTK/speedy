from typing import Any, Iterable, Literal

from speedy import BackgroundTask, BackgroundTasks
from speedy.constants import REDIRECT_ALLOWED_MEDIA_TYPES, REDIRECT_STATUS_CODE
from speedy.datastructures import Cookie
from speedy.enums import MediaType
from speedy.exceptions import ImproperlyConfiguredException
from speedy.response.base import ASGIResponse
from speedy.status_code import HTTP_302_FOUND
from speedy.utils import url_quote

RedirectStatusCode = Literal[301, 302, 303, 307, 308]


class ASGIRedirectResponse(ASGIResponse):
    """A low-level ASGI redirect response class."""

    def __init__(
        self,
        path: str | bytes,
        media_type: str | None = None,
        status_code: RedirectStatusCode | None = None,
        headers: dict[str, Any] | None = None,
        background: BackgroundTask | BackgroundTasks | None = None,
        body: bytes | str = b"",
        content_lenght: int | None = None,
        cookies: Iterable[Cookie] | None = None,
        encoding: str = "utf-8",
        is_head_response: bool = False,
    ):
        headers = {**(headers or {}), "location": url_quote(path)}
        media_type = media_type or MediaType.TEXT
        status_code = status_code or HTTP_302_FOUND

        if status_code not in REDIRECT_STATUS_CODE:
            raise ImproperlyConfiguredException(
                f"`{status_code}` is not a valid for this response. "
                "Redirect responses should have one of "
                f"the following status codes: {', '.join([str(val) for val in REDIRECT_STATUS_CODE])}"
            )

        if media_type not in REDIRECT_ALLOWED_MEDIA_TYPES:
            raise ImproperlyConfiguredException(
                f"`{media_type}` media type is not supported yet. "
                "Media type should be one of "
                f"the following values: {', '.join([str(val) for val in REDIRECT_ALLOWED_MEDIA_TYPES])}"
            )

        super().__init__(
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
            is_head_response=is_head_response,
            encoding=encoding,
            cookies=cookies,
            content_length=content_lenght,
            body=body,
        )
