class ASGIApplicationException(Exception):
    pass


class EmptyException(ASGIApplicationException):
    pass


class ConvertorTypeException(ASGIApplicationException):
    pass
