from functools import lru_cache
from http.cookies import _unquote as unquote_cookie
from urllib.parse import parse_qsl, unquote


@lru_cache(1024)
def parse_query_string(query: bytes | str) -> tuple[tuple[str, str], ...]:
    """ Parse a query string info a tuple of key value parse. """
    if isinstance(query, bytes):
        query = query.decode('latin-1')
    return tuple(parse_qsl(query, keep_blank_values=True, separator='&'))


@lru_cache(1024)
def parse_cookie_string(cookie_string: str) -> dict[str, str]:
    """ Parse a cookie string info a dict of key value parse. """
    cookies = [
        cookie.split("=", 1)
        if "=" in cookie
        else ("", cookie)
        for cookie in cookie_string.split(";")
    ]
    output: dict[str, str] = {
        k: unquote(unquote_cookie(v))
        for k, v in filter(
            lambda x: x[0] or x[1],
            (
                (k.strip(), v.strip()) for k, v in cookies
            ),
        )
    }
    return output
