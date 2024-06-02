from typing import Any, ParamSpec, Callable, Sequence

from speedy.utils.sync import ensure_async_callable

P = ParamSpec('P')


class BackgroundTask:
    """ A container for a background task function. """

    def __init__(self, func: Callable[P, Any], *args: P.args, **kwargs: P.kwargs) -> None:
        self.func = func
        self.args = args
        self.kwargs = kwargs

    async def __call__(self) -> None:
        await ensure_async_callable(self.func)(*self.args, **self.kwargs)


class BackgroundTasks:
    """ A container for a background task functions. """

    def __init__(self, tasks: Sequence['BackgroundTask'] | None = None) -> None:
        self.tasks = list(tasks) if tasks else []

    async def __call__(self):
        for task in self.tasks:
            await task()

    def add_task(self, func: Callable[P, Any], *args: P.args, **kwargs: P.kwargs) -> None:
        """ Add a function to a background task. """
        self.tasks.append(BackgroundTask(func, *args, **kwargs))
