from typing import TypeAlias, TypeVar, Awaitable, Literal

T = TypeVar("T")

SyncOrAsyncUnion: TypeAlias = T | Awaitable[T]

AnyIOBackend: TypeAlias = Literal["asyncio", "trio"]

SAMESITE = Literal["lax", "strict", "none"]
