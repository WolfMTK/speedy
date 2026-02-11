from typing import Final

from speedy.enums import MediaType

ONE_MEGABYTE: Final = 1024 * 1024

MULTIPART_FORM_PART_LIMIT: Final = 1000

REQUEST_MAX_BODY_SIZE: Final = 10_000_000

REDIRECT_STATUS_CODE: Final = {301, 302, 303, 307, 308}

REDIRECT_ALLOWED_MEDIA_TYPES: Final = {MediaType.TEXT, MediaType.HTML, MediaType.JSON}

DEFAULT_ALLOWED_CORS_HEADERS: Final = {
    "Accept",
    "Accept-Language",
    "Content-Language",
    "Content-Type",
}

ZERO = 0
