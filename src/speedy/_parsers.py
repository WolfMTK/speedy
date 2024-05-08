from functools import lru_cache
from urllib.parse import parse_qsl


@lru_cache(1024)
def parse_query_string(query: bytes) -> tuple[tuple[bytes, bytes], ...]:
    """ Parse a query string info a tuple of key value parse. """
    return tuple(parse_qsl(query, separator='&'))
