import pytest

from meilisearch_python_async.errors import MeiliSearchTimeoutError
from meilisearch_python_async.task import get_task, get_tasks, wait_for_task


@pytest.mark.asyncio
async def test_get_tasks(empty_index, small_movies):
    index = await empty_index()
    tasks = await get_tasks(index.http_client)
    current_tasks = len(tasks)
    response = await index.add_documents(small_movies)
    await wait_for_task(index.http_client, response.uid)
    response = await index.add_documents(small_movies)
    await wait_for_task(index.http_client, response.uid)
    response = await get_tasks(index.http_client)
    assert len(response) - current_tasks == 2


@pytest.mark.asyncio
async def test_get_task(empty_index, small_movies):
    index = await empty_index()
    response = await index.add_documents(small_movies)
    await wait_for_task(index.http_client, response.uid)
    update = await get_task(index.http_client, response.uid)
    assert update.status == "succeeded"


@pytest.mark.asyncio
async def test_wait_for_task(empty_index, small_movies):
    index = await empty_index()
    response = await index.add_documents(small_movies)
    update = await wait_for_task(index.http_client, response.uid)
    assert update.status == "succeeded"


@pytest.mark.asyncio
async def test_wait_for_pending_update_time_out(empty_index, small_movies):
    index = await empty_index()
    with pytest.raises(MeiliSearchTimeoutError):
        response = await index.add_documents(small_movies)
        await wait_for_task(index.http_client, response.uid, timeout_in_ms=1, interval_in_ms=1)

    await wait_for_task(
        index.http_client, response.uid
    )  # Make sure the indexing finishes so subsequent tests don't have issues.
