import math
import uuid
from typing import ClassVar

from speedy.exceptions.base import EmptyException
from speedy.exceptions.route import PathException

ZERO = 0


class Convertor[T]:
    regex: ClassVar[str] = ''

    def convert(self, value: str) -> T:
        raise NotImplementedError()

    def to_string(self, value: T) -> str:
        raise NotImplementedError()


class StringConvertor(Convertor[str]):
    regex = '[^/]+'

    def convert(self, value: str) -> str:
        return value

    def to_string(self, value: str) -> str:
        value = str(value)
        if '/' in value:
            raise PathException('May not contain path separators')
        if not value:
            raise EmptyException('Must not be empty')
        return value


class PathConvertor(Convertor[str]):
    regex = '.*'

    def convert(self, value: str) -> str:
        return str(value)

    def to_string(self, value: str) -> str:
        return str(value)


class IntegerConvertor(Convertor[int]):
    regex = '[0-9]+'

    def convert(self, value: str) -> int:
        return int(value)

    def to_string(self, value: int) -> str:
        value = int(value)
        if value < ZERO:
            raise EmptyException('Negative integers are not supported')
        return str(value)


class FloatConvertor(Convertor[float]):
    regex = r'[0-9]+(\.[0-9]+)?'

    def convert(self, value: str) -> float:
        return float(value)

    def to_string(self, value: float) -> str:
        value = float(value)
        if value < ZERO:
            raise EmptyException('Negative integers are not supported')
        if math.isnan(value):
            raise EmptyException('NaN values are not supported')
        if math.isinf(value):
            raise EmptyException('Infinite values are not supported')
        return f'{value:0.20f}'.rstrip('0').rstrip('.')


class UUIDConvertor(Convertor[uuid.UUID]):
    regex = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'

    def convert(self, value: str) -> uuid.UUID:
        return uuid.UUID(value)

    def to_string(self, value: uuid.UUID) -> str:
        return str(value)


CONVERTOR_TYPES = {
    'str': StringConvertor(),
    'path': PathConvertor(),
    'int': IntegerConvertor(),
    'float': FloatConvertor(),
    'uuid': UUIDConvertor(),
}
