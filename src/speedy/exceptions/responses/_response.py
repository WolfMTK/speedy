from dataclasses import dataclass, field, asdict
from typing import Any

from speedy.enums import MediaType
from speedy.connection import Request
from speedy.exceptions import HTTPException
from speedy.exceptions.base import SpeedyException
from speedy.exceptions.responses import base
from speedy.response import Response
from speedy.serialization import encode_json, get_serializer
from speedy.status_code import HTTP_500_INTERNAL_SERVER_ERROR


@dataclass(slots=True)
class ExceptionResponseContent:
    """ Represent the contents of an exception-response. """

    status_code: int
    detail: str
    media_type: MediaType | str
    headers: dict[str, str] | None = field(default=None)
    extra: dict[str, Any] | list[Any] | None = field(default=None)

    def to_response(self, request: Request | None = None) -> Response:
        """ Create a response from the model attributes. """
        content = {key: val for key, val in asdict(self).items() if key not in ("headers", "media_type") and val is not None}
        type_encoders = base._get_type_encoders_for_request(request) if request is not None else None
        if self.media_type != MediaType.JSON:
            content = encode_json(content, get_serializer())
        return Response(
            content=content,
            headers=self.headers,
            status_code=self.status_code,
            media_type=self.media_type,
            type_encoders=type_encoders,
        )


def create_exception_response(request: Request[Any, Any, Any], exc: Exception) -> Response:
    """ Construct a response from an exception. """

    headers: dict[str, Any] | None = None
    extra: dict[str, Any] | list[Any] | None = None
    status_code = HTTP_500_INTERNAL_SERVER_ERROR

    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        headers = exc.headers
        extra = exc.extra

    detail = (
        exc.detail
        if isinstance(exc, SpeedyException) and status_code != HTTP_500_INTERNAL_SERVER_ERROR
        else "Internal Server Error"
    )

    try:
        media_type = request.route_handler.media_type
    except (KeyError, AttributeError):
        media_type = MediaType.JSON

    content = ExceptionResponseContent(
        status_code=status_code,
        detail=detail,
        headers=headers,
        extra=extra,
        media_type=media_type,
    )
    return content.to_response(request)
