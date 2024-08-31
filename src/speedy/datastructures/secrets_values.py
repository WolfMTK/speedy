from abc import abstractmethod, ABC
from typing import Generic, TypeVar, Union

SecretType = TypeVar('SecretType', bound=Union[str, bytes])


class BaseSecret(ABC, Generic[SecretType]):
    def __init__(self, value: SecretType) -> None:
        self._value = value

    def __str__(self) -> str:
        return str(self.get_obscured())

    def __repr__(self) -> str:
        return f'{type(self).__name__}({self.get_obscured()!r})'

    def __bool__(self) -> bool:
        return bool(self._value)

    def get_secret_value(self) -> SecretType:
        """ Return the actual secret value. """
        return self._value

    @abstractmethod
    def get_obscured(self) -> SecretType: ...


class SecretString(BaseSecret[str]):
    """ Represents a secret string value. """

    def get_obscured(self) -> str:
        return '**********'


class SecretBytes(BaseSecret[bytes]):
    """ Represents a secret bytes value. """

    def get_obscured(self) -> bytes:
        return b'**********'
