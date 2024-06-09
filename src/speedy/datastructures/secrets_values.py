from speedy.protocols.secrets_values import AbstractSecret


class SecretString(AbstractSecret[str]):
    """ Represents a secret string value. """

    def get_obscured(self) -> str:
        return '**********'


class SecretBytes(AbstractSecret[bytes]):
    """ Represents a secret bytes value. """

    def get_obscured(self) -> bytes:
        return b'**********'
