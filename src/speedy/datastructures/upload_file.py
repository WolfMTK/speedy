from tempfile import SpooledTemporaryFile
from typing import TypeVar

from speedy.concurrency import sync_to_thread
from speedy.constants import ONE_MEGABYTE

TIME = 0
SIZE_FILE = -1

Headers = TypeVar('Headers')


class UploadFile:
    def __init__(
            self,
            filename: str,
            *,
            file_data: bytes | None = None,
            size: int = ONE_MEGABYTE,
            headers: dict[str, str] | Headers | None = None
    ) -> None:
        self.filename = filename
        self.headers = headers
        self.file = SpooledTemporaryFile(max_size=size)

        if file_data:
            self._write_file(file_data)

    def __repr__(self):
        return f'{type(self).__name__}(filename={self.filename}, headers={self.headers})'

    @property
    def content_type(self) -> str | None:
        """ Get content type from header. """
        return self.headers.get('content-type')

    @property
    def _is_memory(self) -> bool:
        return getattr(self.file, '_rolled', False)

    async def write(self, data: bytes) -> int:
        """ Proxy for data writing. """
        if self._is_memory:
            return await sync_to_thread(self.file.write, data)
        return self.file.write(data)

    async def read(self, size: int = SIZE_FILE) -> bytes:
        """ Proxy for data reading. """
        if self._is_memory:
            return await sync_to_thread(self.file.read, size)
        return self.file.read(size)

    async def seek(self, offset: int) -> int:
        """ Proxy for file seek. """
        if self._is_memory:
            return await sync_to_thread(self.file.seek, offset)
        return self.file.seek(offset)

    async def close(self) -> None:
        """ Proxy for file close. """
        if self._is_memory:
            return await sync_to_thread(self.file.close)
        return self.file.close()

    def _write_file(self, data: bytes | None) -> None:
        self.file.write(data)
        self.file.seek(TIME)
