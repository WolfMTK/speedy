from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Union

SecretType = TypeVar('SecretType', bound=Union[str, bytes])


class AbstractSecret(ABC, Generic[SecretType]):
    """ Represents secret values that can be a string or bits. """

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
    def get_obscured(self) -> SecretType: pass
