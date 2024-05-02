from http import HTTPStatus


class HTTPException(Exception):
    def __init__(
            self,
            status_code: int,
            detail: str | None = None,
            headers: dict[str, str] | None = None
    ) -> None:
        if detail is None:
            detail = HTTPStatus(status_code).phrase
        self.status_code = status_code
        self.detail = detail
        self.headers = headers

    def __str__(self) -> str:
        return f'{self.status_code}: {self.detail}'

    def __repr__(self) -> str:
        return f'{type(self).__name__}(status_code={self.status_code}, detail={self.detail})'
