from speedy._speedy import URL as URL
from speedy._speedy import Address as Address
from speedy._speedy import Headers as Headers
from speedy._speedy import ImmutableMultiDict as ImmutableMultiDict
from speedy._speedy import ImmutableState as ImmutableState
from speedy._speedy import MultiDict as MultiDict
from speedy._speedy import MutableHeaders as MutableHeaders
from speedy._speedy import QueryParams as QueryParams
from speedy._speedy import State as State
from speedy._speedy import UploadFile as _UploadFile
from speedy._speedy import URLPath as URLPath
from speedy.concurrency import run_in_threadpool

__all__ = [
    "URL",
    "Address",
    "FormMultiDict",
    "Headers",
    "ImmutableMultiDict",
    "ImmutableState",
    "MultiDict",
    "MutableHeaders",
    "QueryParams",
    "State",
    "URLPath",
    "UploadFile",
]


class UploadFile(_UploadFile):
    async def write(self, data: bytes) -> int:
        if self.is_spooled_to_disk:
            return await run_in_threadpool(self._write_sync, data)
        return self._write_sync(data)

    async def read(self, size: int = -1) -> bytes:
        if self.is_spooled_to_disk:
            return await run_in_threadpool(self._read_sync, size)
        return self._read_sync(size)

    async def seek(self, offset: int) -> int:
        if self.is_spooled_to_disk:
            return await run_in_threadpool(self._seek_sync, offset)
        return self._seek_sync(offset)

    async def size(self) -> int:
        if self.is_spooled_to_disk:
            return await run_in_threadpool(self._size_sync)
        return self._size_sync()

    async def close(self) -> None:
        if self.is_spooled_to_disk:
            await run_in_threadpool(self._close_sync)
            return
        self._close_sync()


class FormMultiDict(ImmutableMultiDict):
    """MultiDict for form data."""

    async def close(self) -> None:
        """Close all files in the multi-dict."""
        for _, value in self.multi_items():
            if isinstance(value, UploadFile):
                await value.close()
