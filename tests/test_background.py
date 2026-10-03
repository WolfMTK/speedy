import pytest

from speedy.background import BackgroundTask, BackgroundTasks
from speedy.responses import Response
from speedy.types import Receive, Scope, Send
from tests.types import TestClientFactory


class TestBackgroundTask:
    def test_async_task(self, test_client_factory: TestClientFactory) -> None:
        TASK_COMPLETE = False

        async def async_task() -> None:
            nonlocal TASK_COMPLETE
            TASK_COMPLETE = True

        task = BackgroundTask(async_task)

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            response = Response("task initiated", media_type="text/plain", background=task)
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.text == "task initiated"
        assert TASK_COMPLETE

    def test_sync_task(self, test_client_factory: TestClientFactory) -> None:
        TASK_COMPLETE = False

        def sync_task() -> None:
            nonlocal TASK_COMPLETE
            TASK_COMPLETE = True

        task = BackgroundTask(sync_task)

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            response = Response("task initiated", media_type="text/plain", background=task)
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.text == "task initiated"
        assert TASK_COMPLETE


class TestBackgroundTasks:
    def test_multiple_tasks(self, test_client_factory: TestClientFactory) -> None:
        TASK_COUNTER = 0

        def increment(amount: int) -> None:
            nonlocal TASK_COUNTER
            TASK_COUNTER += amount

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            tasks = BackgroundTasks()
            tasks.add_task(increment, amount=1)
            tasks.add_task(increment, amount=2)
            tasks.add_task(increment, amount=3)
            response = Response("tasks initiated", media_type="text/plain", background=tasks)
            await response(scope, receive, send)

        client = test_client_factory(app)
        response = client.get("/")
        assert response.text == "tasks initiated"
        assert TASK_COUNTER == 1 + 2 + 3

    def test_failure_avoids_next_execution(self, test_client_factory: TestClientFactory) -> None:
        TASK_COUNTER = 0

        def increment() -> None:
            nonlocal TASK_COUNTER
            TASK_COUNTER += 1
            if TASK_COUNTER == 1:
                raise Exception("task failed")

        async def app(scope: Scope, receive: Receive, send: Send) -> None:
            tasks = BackgroundTasks()
            tasks.add_task(increment)
            tasks.add_task(increment)
            response = Response("tasks initiated", media_type="text/plain", background=tasks)
            await response(scope, receive, send)

        client = test_client_factory(app)
        with pytest.raises(Exception, match="task failed"):
            client.get("/")
        assert TASK_COUNTER == 1
