import asyncio
from uuid import uuid4

from examples.async_add_documents_decorator import load_documents
from examples.async_add_documents_in_batches import add_documents_in_batches
from examples.async_search_tracker import SearchTrackerPlugin, search
from examples.async_search_tracker import add_documents as search_tracker_add_documents
from examples.async_update_settings import add_documents as update_settings_add_documents
from examples.async_update_settings import update_settings
from meilisearch_python_sdk.plugins import AsyncIndexPlugins


async def test_add_documents_decorator(small_movies_path, async_client):
    index = await async_client.create_index("movies", "id")
    await load_documents(small_movies_path)
    result = await async_client.get_tasks()
    await asyncio.gather(*[async_client.wait_for_task(x.uid) for x in result.results])
    documents = await index.get_documents()

    assert len(documents.results) > 0


async def test_add_documents_in_batchees(small_movies_path, async_empty_index, async_client):
    index = await async_empty_index()
    tasks = await add_documents_in_batches(index, small_movies_path)
    for task in tasks:
        await async_client.wait_for_task(task.task_uid)
        result = await async_client.get_task(task.task_uid)
        assert result.status == "succeeded"


async def test_search_tracker(small_movies_path, async_client, tmp_path):
    db_path = tmp_path / "search_tracker.db"
    plugins = AsyncIndexPlugins(search_plugins=(SearchTrackerPlugin(db_path),))
    index = await async_client.create_index(
        uid=str(uuid4()), primary_key="id", plugins=plugins, timeout_in_ms=5000
    )
    task = await search_tracker_add_documents(index, small_movies_path)
    await async_client.wait_for_task(task.task_uid)
    result = await async_client.get_task(task.task_uid)
    assert result.status == "succeeded"
    result = await search(index, "Cars")
    assert len(result.hits) > 0


async def test_update_settings(small_movies_path, async_empty_index, async_client):
    index = await async_empty_index()
    task = await update_settings(index)
    await async_client.wait_for_task(task.task_uid)
    task = await update_settings_add_documents(index, small_movies_path)
    await async_client.wait_for_task(task.task_uid)
    result = await async_client.get_task(task.task_uid)
    assert result.status == "succeeded"
