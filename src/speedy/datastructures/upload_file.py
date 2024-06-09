from tempfile import SpooledTemporaryFile

from speedy.concurrency import sync_to_thread
from speedy.constants import ONE_MEGABYTE

TIME = 0
SIZE_FILE = -1


class UploadFile:
    def __init__(
            self,
            filename: str,
            *,
            file_data: bytes | None = None,
            size: int = ONE_MEGABYTE,
            headers: dict[str, str] | None = None
    ) -> None:
        self.filename = filename
        self.headers = headers
        self.file = SpooledTemporaryFile(max_size=size)

        if file_data:
            self._write_file(file_data)

    @property
    def content_type(self) -> str | None:
        return self.headers.get('content-type')

    @property
    def is_memory(self) -> bool:
        return getattr(self.file, '_rolled', False)

    async def write(self, data: bytes) -> int:
        """ Proxy for data writing. """
        if self.is_memory:
            return await sync_to_thread(self.file.write, data)
        return self.file.write(data)

    async def read(self, size: int = SIZE_FILE) -> bytes:
        """ Proxy for data reading. """
        if self.is_memory:
            return await sync_to_thread(self.file.read, size)
        return self.file.read(size)

    async def seek(self, offset: int) -> int:
        """ Proxy for file seek. """
        if self.is_memory:
            return await sync_to_thread(self.file.seek, offset)
        return self.file.seek(offset)

    async def close(self) -> None:
        """ Proxy for file close. """
        if self.is_memory:
            return await sync_to_thread(self.file.close)
        return self.file.close()

    def _write_file(self, data: bytes | None) -> None:
        self.file.write(data)
        self.file.seek(TIME)
