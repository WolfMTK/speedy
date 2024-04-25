from abc import abstractmethod, ABC


class HTTPMethods(ABC):
    @abstractmethod
    def get(self, path: str): ...

    @abstractmethod
    def put(self, path: str): ...

    @abstractmethod
    def post(self, path: str): ...

    @abstractmethod
    def delete(self, path: str): ...

    @abstractmethod
    def options(self, path: str): ...

    @abstractmethod
    def head(self, path: str): ...

    @abstractmethod
    def path(self, path: str): ...

    @abstractmethod
    def trace(self, path: str): ...
