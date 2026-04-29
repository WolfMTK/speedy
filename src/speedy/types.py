from typing import Literal

from speedy.enums import HTTPMethod

type HTTPMethodName = Literal["GET", "POST", "DELETE", "PATCH", "PUT", "HEAD", "TRACE", "OPTIONS"]

type Method = HTTPMethodName | HTTPMethod
