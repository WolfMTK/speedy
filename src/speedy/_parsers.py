from collections import defaultdict
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
        cookie.split('=', 1)
        if '=' in cookie
        else ('', cookie)
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


@lru_cache(1024)
def parse_url_encoded_form_data(encoded_data: bytes) -> dict[str, str | list[str]]:
    """ Parse an url encoded form data dict. """
    decoded = defaultdict(list)
    for key, value in parse_qsl(encoded_data.decode('latin-1'), separator='&', keep_blank_values=True):
        decoded[key].append(value)
    return {
        key: value
        if len(value) > 1 else value[0]
        for key, value in decoded.items()
    }
