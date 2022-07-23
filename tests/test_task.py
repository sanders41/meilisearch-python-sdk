import pytest

from meilisearch_python_async.errors import MeiliSearchTimeoutError
from meilisearch_python_async.task import get_task, get_tasks, wait_for_task


async def test_get_tasks(empty_index, small_movies):
    index = await empty_index()
    tasks = await get_tasks(index.http_client)
    current_tasks = len(tasks)
    response = await index.add_documents(small_movies)
    await wait_for_task(index.http_client, response.task_uid)
    response = await index.add_documents(small_movies)
    await wait_for_task(index.http_client, response.task_uid)
    response = await get_tasks(index.http_client)
    assert len(response) >= current_tasks


async def test_get_tasks_for_index(empty_index, small_movies):
    index = await empty_index()
    tasks = await get_tasks(index.http_client, index.uid)
    current_tasks = len(tasks)
    response = await index.add_documents(small_movies)
    await wait_for_task(index.http_client, response.task_uid)
    response = await index.add_documents(small_movies)
    await wait_for_task(index.http_client, response.task_uid)
    response = await get_tasks(index.http_client, index.uid)
    assert len(response) >= current_tasks


async def test_get_task(empty_index, small_movies):
    index = await empty_index()
    response = await index.add_documents(small_movies)
    await wait_for_task(index.http_client, response.task_uid)
    update = await get_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"


async def test_wait_for_task(empty_index, small_movies):
    index = await empty_index()
    response = await index.add_documents(small_movies)
    update = await wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"


async def test_wait_for_pending_update_time_out(empty_index, small_movies):
    index = await empty_index()
    with pytest.raises(MeiliSearchTimeoutError):
        response = await index.add_documents(small_movies)
        await wait_for_task(index.http_client, response.task_uid, timeout_in_ms=1, interval_in_ms=1)

    await wait_for_task(  # Make sure the indexing finishes so subsequent tests don't have issues.
        index.http_client, response.task_uid
    )
