import pytest

from meilisearch_python_async.errors import MeiliSearchTimeoutError
from meilisearch_python_async.task import (
    cancel_tasks,
    delete_tasks,
    get_task,
    get_tasks,
    wait_for_task,
)


@pytest.fixture
async def create_tasks(empty_index, small_movies):
    """Ensures there are some tasks present for testing."""
    index = await empty_index()
    await index.update_ranking_rules(["type", "exactness"])
    await index.reset_ranking_rules()
    await index.add_documents(small_movies)
    await index.add_documents(small_movies)


@pytest.mark.usefixtures("create_tasks")
async def test_cancel_statuses(test_client):
    task = await cancel_tasks(test_client.http_client, statuses=["enqueued", "processing"])
    await wait_for_task(test_client.http_client, task.task_uid)
    completed_task = await get_task(test_client.http_client, task.task_uid)
    tasks = await get_tasks(test_client.http_client, types="taskCancelation")

    assert completed_task.index_uids is None
    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks[0].details is not None
    assert "statuses=enqueued%2Cprocessing" in tasks[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_cancel_tasks(test_client):
    task = await cancel_tasks(test_client.http_client, uids=["1", "2"])
    await wait_for_task(test_client.http_client, task.task_uid)
    completed_task = await get_task(test_client.http_client, task.task_uid)
    tasks = await get_tasks(test_client.http_client, types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks[0].details is not None
    assert "uids=1%2C2" in tasks[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_cancel_task_no_params(test_client):
    task = await cancel_tasks(test_client.http_client)
    await wait_for_task(test_client.http_client, task.task_uid)
    completed_task = await get_task(test_client.http_client, task.task_uid)
    tasks = await get_tasks(test_client.http_client, types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks[0].details is not None
    assert "statuses=enqueued%2Cprocessing" in tasks[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_delete_statuses(test_client):
    task = await delete_tasks(test_client.http_client, statuses=["enqueued", "processing"])
    await wait_for_task(test_client.http_client, task.task_uid)
    deleted_tasks = await get_task(test_client.http_client, task.task_uid)
    tasks = await get_tasks(test_client.http_client, types="taskDeletion")

    assert deleted_tasks.status == "succeeded"
    assert deleted_tasks.task_type == "taskDeletion"
    assert tasks[0].details is not None
    assert "statuses=enqueued%2Cprocessing" in tasks[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_delete_tasks(test_client):
    task = await delete_tasks(test_client.http_client, uids=["1", "2"])
    await wait_for_task(test_client.http_client, task.task_uid)
    completed_task = await get_task(test_client.http_client, task.task_uid)
    tasks = await get_tasks(test_client.http_client, types="taskDeletion")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskDeletion"
    assert tasks[0].details is not None
    assert "uids=1%2C2" in tasks[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_delete_no_params(test_client):
    task = await delete_tasks(test_client.http_client)
    await wait_for_task(test_client.http_client, task.task_uid)
    deleted_tasks = await get_task(test_client.http_client, task.task_uid)
    tasks = await get_tasks(test_client.http_client, types="taskDeletion")

    assert deleted_tasks.status == "succeeded"
    assert deleted_tasks.task_type == "taskDeletion"
    assert tasks[0].details is not None
    assert (
        "statuses=canceled%2Cenqueued%2Cfailed%2Cprocessing%2Csucceeded"
        in tasks[0].details["originalFilter"]
    )


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
    tasks = await get_tasks(index.http_client, index_ids=[index.uid])
    current_tasks = len(tasks)
    response = await index.add_documents(small_movies)
    await wait_for_task(index.http_client, response.task_uid)
    response = await index.add_documents(small_movies)
    await wait_for_task(index.http_client, response.task_uid)
    response = await get_tasks(index.http_client, index_ids=[index.uid])
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
