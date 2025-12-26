from speedy.connection import Request
from speedy.types import TypeEncodersMap


def _get_type_encoders_for_request(request: Request) -> TypeEncodersMap | None:
    try:
        return request.route_handler.type_encoders
    except (KeyError, AttributeError):
        return request.app.type_encoders
