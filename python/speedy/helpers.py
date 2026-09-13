import re
from dataclasses import dataclass
from ipaddress import AddressValueError, IPv6Address

from speedy.types import Scope

_HOST_RE = re.compile(
    r"^(?P<host>[a-z0-9._~%!$&'()*+,;=-]+|\[(?:(?P<ipv6>[a-f0-9]*:[a-f0-9.:]+)|"
    r"(?-i:v)[a-f0-9]+\.[a-z0-9._~!$&'()*+,;=:-]+)\])(?::(?P<port>[0-9]+))?$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ParsedHost:
    host: str
    port: str | None

    @property
    def authority(self) -> str:
        return self.host if self.port is None else f"{self.host}:{self.port}"

    @property
    def is_valid_port(self) -> bool:
        if self.port is None:
            return True
        port = self.port.lstrip("0")
        return len(port) <= 5 and int(port or "0") <= 65535


def parse_host_header(host_header: str | None) -> ParsedHost | None:
    if host_header is None:
        return None

    match = _HOST_RE.fullmatch(host_header)
    if match is None:
        return None

    ipv6 = match["ipv6"]
    if ipv6 is not None:
        try:
            IPv6Address(ipv6)
        except AddressValueError:
            return None

    return ParsedHost(match["host"], match["port"])


def get_route_path(scope: Scope) -> str:
    path: str = scope["path"]
    root_path: str = scope.get("root_path", "")
    if not root_path:
        return path

    if not path.startswith(root_path):
        return path

    if path == root_path:
        return ""

    if path[len(root_path)] == "/":
        return path[len(root_path) :]

    return path
