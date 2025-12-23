from typing import Final


class AsyncLibraryNotFoundError(RuntimeError):
    pass


_LIB_ASYNCIO: Final = "asyncio"
_LIB_TRIO: Final = "trio"


def current_async_library() -> str:
    """ Detect which async library is currently running. """
    libs = {
        _LIB_TRIO: lambda: bool(__import__(_LIB_TRIO).lowlevel.current_task()),
        _LIB_ASYNCIO: lambda: __import__(_LIB_ASYNCIO).current_task() is not None,
    }

    for lib_name, check in libs.items():
        try:
            if check():
                return lib_name
        except RuntimeError:
            continue
        except ImportError:
            continue
    raise AsyncLibraryNotFoundError(
        "unknown async library, or not in async context"
    )
