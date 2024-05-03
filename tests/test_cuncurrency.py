import asyncio

from speedy.concurrency import sync_to_thread


def func():
    return 1


def test_sync_to_thread():
    loop = asyncio.new_event_loop()
    assert loop.run_until_complete(sync_to_thread(func)) == 1
