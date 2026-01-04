from typing import Sequence

from speedy.enums import HttpMethod
from speedy.exceptions import ValidationException
from speedy.types import Method, HttpMethodName

HTTP_METHOD_NAMES = {method.value for method in HttpMethod}


def normalize_http_method(http_methods: Method | Sequence[Method]) -> set[HttpMethodName]:
    """ Normalize HTTP method(s) into a set of upper-case method names. """
    if isinstance(http_methods, HttpMethod) or isinstance(http_methods, str):
        http_methods = [http_methods]

    output = set()
    for method in http_methods:
        method_name = method.value.upper() if isinstance(method, HttpMethod) else method.upper()
        if method_name not in HTTP_METHOD_NAMES:
            raise ValidationException(f"Invalid HTTP method: `{method_name}`")
        output.add(method_name)

    return output
