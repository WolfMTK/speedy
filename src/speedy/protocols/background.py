from abc import ABC, abstractmethod


class AbstractBackground(ABC):
    """ Abstract a container for a 'background' task function. """

    @abstractmethod
    async def __call__(self) -> None: ...
