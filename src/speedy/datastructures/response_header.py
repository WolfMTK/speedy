from dataclasses import dataclass


@dataclass
class ResponseHeader:
    """ Container type for a response header. """
    name: str
    """ Header name """

    value: str | None = None
    """ Value to set for the response header. """
