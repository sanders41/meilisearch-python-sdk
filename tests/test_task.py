from datetime import datetime
from urllib.parse import quote_plus

import httpx
import pytest
from httpx import AsyncClient

from meilisearch_python_async.errors import MeilisearchTaskFailedError, MeilisearchTimeoutError
from meilisearch_python_async.task import (
    async_cancel_tasks,
    async_delete_tasks,
    async_get_task,
    async_get_tasks,
    async_wait_for_task,
)


@pytest.fixture
async def create_tasks(empty_index, small_movies):
    """Ensures there are some tasks present for testing."""
    index = await empty_index()
    await index.update_ranking_rules(["typo", "exactness"])
    await index.reset_ranking_rules()
    await index.add_documents(small_movies)
    await index.add_documents(small_movies)


@pytest.mark.usefixtures("create_tasks")
async def test_cancel_statuses(async_test_client):
    task = await async_cancel_tasks(async_test_client, statuses=["enqueued", "processing"])
    await async_wait_for_task(async_test_client, task.task_uid)
    completed_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskCancelation")

    assert completed_task.index_uid is None
    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "statuses=enqueued%2Cprocessing" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_async_cancel_tasks_uids(async_test_client):
    task = await async_cancel_tasks(async_test_client, uids=["1", "2"])
    await async_wait_for_task(async_test_client, task.task_uid)
    completed_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "uids=1%2C2" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_async_cancel_tasks_index_uids(async_test_client):
    task = await async_cancel_tasks(async_test_client, index_uids=["1"])

    await async_wait_for_task(async_test_client, task.task_uid)
    completed_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "indexUids=1" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_async_cancel_tasks_types(async_test_client):
    task = await async_cancel_tasks(async_test_client, types=["taskDeletion"])
    await async_wait_for_task(async_test_client, task.task_uid)
    completed_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "types=taskDeletion" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_async_cancel_tasks_before_enqueued_at(async_test_client):
    before = datetime.now()
    task = await async_cancel_tasks(async_test_client, before_enqueued_at=before)
    await async_wait_for_task(async_test_client, task.task_uid)
    completed_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert (
        f"beforeEnqueuedAt={quote_plus(before.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
async def test_async_cancel_tasks_after_enqueued_at(async_test_client):
    after = datetime.now()
    task = await async_cancel_tasks(async_test_client, after_enqueued_at=after)
    await async_wait_for_task(async_test_client, task.task_uid)
    completed_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert (
        f"afterEnqueuedAt={quote_plus(after.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
async def test_async_cancel_tasks_before_started_at(async_test_client):
    before = datetime.now()
    task = await async_cancel_tasks(async_test_client, before_started_at=before)
    await async_wait_for_task(async_test_client, task.task_uid)
    completed_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert (
        f"beforeStartedAt={quote_plus(before.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
async def test_async_cancel_tasks_after_finished_at(async_test_client):
    after = datetime.now()
    task = await async_cancel_tasks(async_test_client, after_finished_at=after)
    await async_wait_for_task(async_test_client, task.task_uid)
    completed_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert (
        f"afterFinishedAt={quote_plus(after.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
async def test_cancel_task_no_params(async_test_client):
    task = await async_cancel_tasks(async_test_client)
    await async_wait_for_task(async_test_client, task.task_uid)
    completed_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskCancelation")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskCancelation"
    assert tasks.results[0].details is not None
    assert "statuses=enqueued%2Cprocessing" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_delete_statuses(async_test_client):
    task = await async_delete_tasks(async_test_client, statuses=["enqueued", "processing"])
    await async_wait_for_task(async_test_client, task.task_uid)
    deleted_tasks = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskDeletion")

    assert deleted_tasks.status == "succeeded"
    assert deleted_tasks.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert "statuses=enqueued%2Cprocessing" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_async_delete_tasks(async_test_client):
    task = await async_delete_tasks(async_test_client, uids=["1", "2"])
    await async_wait_for_task(async_test_client, task.task_uid)
    completed_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskDeletion")

    assert completed_task.status == "succeeded"
    assert completed_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert "uids=1%2C2" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_async_delete_tasks_index_uids(async_test_client):
    task = await async_delete_tasks(async_test_client, index_uids=["1"])
    await async_wait_for_task(async_test_client, task.task_uid)
    deleted_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert "indexUids=1" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_async_delete_tasks_types(async_test_client):
    task = await async_delete_tasks(async_test_client, types=["taskDeletion"])
    await async_wait_for_task(async_test_client, task.task_uid)
    deleted_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert "types=taskDeletion" in tasks.results[0].details["originalFilter"]


@pytest.mark.usefixtures("create_tasks")
async def test_async_delete_tasks_before_enqueued_at(async_test_client):
    before = datetime.now()
    task = await async_delete_tasks(async_test_client, before_enqueued_at=before)
    await async_wait_for_task(async_test_client, task.task_uid)
    deleted_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        f"beforeEnqueuedAt={quote_plus(before.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
async def test_async_delete_tasks_after_enqueued_at(async_test_client):
    after = datetime.now()
    task = await async_delete_tasks(async_test_client, after_enqueued_at=after)
    await async_wait_for_task(async_test_client, task.task_uid)
    deleted_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        f"afterEnqueuedAt={quote_plus(after.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
async def test_async_delete_tasks_before_started_at(async_test_client):
    before = datetime.now()
    task = await async_delete_tasks(async_test_client, before_started_at=before)
    await async_wait_for_task(async_test_client, task.task_uid)
    deleted_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        f"beforeStartedAt={quote_plus(before.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
async def test_async_delete_tasks_after_finished_at(async_test_client):
    after = datetime.now()
    task = await async_delete_tasks(async_test_client, after_finished_at=after)
    await async_wait_for_task(async_test_client, task.task_uid)
    deleted_task = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskDeletion")

    assert deleted_task.status == "succeeded"
    assert deleted_task.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        f"afterFinishedAt={quote_plus(after.isoformat())}Z"
        in tasks.results[0].details["originalFilter"]
    )


@pytest.mark.usefixtures("create_tasks")
async def test_delete_no_params(async_test_client):
    task = await async_delete_tasks(async_test_client)
    await async_wait_for_task(async_test_client, task.task_uid)
    deleted_tasks = await async_get_task(async_test_client, task.task_uid)
    tasks = await async_get_tasks(async_test_client, types="taskDeletion")

    assert deleted_tasks.status == "succeeded"
    assert deleted_tasks.task_type == "taskDeletion"
    assert tasks.results[0].details is not None
    assert (
        "statuses=canceled%2Cenqueued%2Cfailed%2Cprocessing%2Csucceeded"
        in tasks.results[0].details["originalFilter"]
    )


async def test_async_get_tasks(empty_index, small_movies):
    index = await empty_index()
    tasks = await async_get_tasks(index.http_client)
    current_tasks = len(tasks.results)
    response = await index.add_documents(small_movies)
    await async_wait_for_task(index.http_client, response.task_uid)
    response = await index.add_documents(small_movies)
    await async_wait_for_task(index.http_client, response.task_uid)
    response = await async_get_tasks(index.http_client)
    assert len(response.results) >= current_tasks


async def test_async_get_tasks_for_index(empty_index, small_movies):
    index = await empty_index()
    tasks = await async_get_tasks(index.http_client, index_ids=[index.uid])
    current_tasks = len(tasks.results)
    response = await index.add_documents(small_movies)
    await async_wait_for_task(index.http_client, response.task_uid)
    response = await index.add_documents(small_movies)
    await async_wait_for_task(index.http_client, response.task_uid)
    response = await async_get_tasks(index.http_client, index_ids=[index.uid])
    assert len(response.results) >= current_tasks
    uid = set([x.index_uid for x in response.results])
    assert len(uid) == 1
    assert next(iter(uid)) == index.uid


async def test_async_get_task(empty_index, small_movies):
    index = await empty_index()
    response = await index.add_documents(small_movies)
    await async_wait_for_task(index.http_client, response.task_uid)
    update = await async_get_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"


async def test_async_wait_for_task(empty_index, small_movies):
    index = await empty_index()
    response = await index.add_documents(small_movies)
    update = await async_wait_for_task(index.http_client, response.task_uid)
    assert update.status == "succeeded"


async def test_async_wait_for_task_no_timeout(empty_index, small_movies):
    index = await empty_index()
    response = await index.add_documents(small_movies)
    update = await async_wait_for_task(index.http_client, response.task_uid, timeout_in_ms=None)
    assert update.status == "succeeded"


async def test_wait_for_pending_update_time_out(empty_index, small_movies):
    index = await empty_index()
    with pytest.raises(MeilisearchTimeoutError):
        response = await index.add_documents(small_movies)
        await async_wait_for_task(
            index.http_client, response.task_uid, timeout_in_ms=1, interval_in_ms=1
        )

    await async_wait_for_task(  # Make sure the indexing finishes so subsequent tests don't have issues.
        index.http_client, response.task_uid
    )


async def test_async_wait_for_task_raise_for_status_true(empty_index, small_movies):
    index = await empty_index()
    response = await index.add_documents(small_movies)
    update = await async_wait_for_task(index.http_client, response.task_uid, raise_for_status=True)
    assert update.status == "succeeded"


async def test_async_wait_for_task_raise_for_status_true_no_timeout(
    empty_index, small_movies, base_url, monkeypatch
):
    async def mock_get_response(*args, **kwargs):
        task = {
            "uid": args[1].split("/")[1],
            "index_uid": "7defe207-8165-4b69-8170-471456e295e0",
            "status": "failed",
            "task_type": "indexDeletion",
            "details": {"deletedDocuments": 30},
            "error": None,
            "canceled_by": None,
            "duration": "PT0.002765250S",
            "enqueued_at": "2023-06-09T01:03:48.311936656Z",
            "started_at": "2023-06-09T01:03:48.314143377Z",
            "finished_at": "2023-06-09T01:03:48.316536088Z",
        }

        return httpx.Response(
            200, json=task, request=httpx.Request("get", url=f"{base_url}/{args[1]}")
        )

    index = await empty_index()
    response = await index.add_documents(small_movies)
    monkeypatch.setattr(AsyncClient, "get", mock_get_response)
    with pytest.raises(MeilisearchTaskFailedError):
        await async_wait_for_task(
            index.http_client, response.task_uid, raise_for_status=True, timeout_in_ms=None
        )


async def test_async_wait_for_task_raise_for_status_false(
    empty_index, small_movies, base_url, monkeypatch
):
    async def mock_get_response(*args, **kwargs):
        task = {
            "uid": args[1].split("/")[1],
            "index_uid": "7defe207-8165-4b69-8170-471456e295e0",
            "status": "failed",
            "task_type": "indexDeletion",
            "details": {"deletedDocuments": 30},
            "error": None,
            "canceled_by": None,
            "duration": "PT0.002765250S",
            "enqueued_at": "2023-06-09T01:03:48.311936656Z",
            "started_at": "2023-06-09T01:03:48.314143377Z",
            "finished_at": "2023-06-09T01:03:48.316536088Z",
        }
        return httpx.Response(
            200, json=task, request=httpx.Request("get", url=f"{base_url}/{args[1]}")
        )

    index = await empty_index()
    response = await index.add_documents(small_movies)
    monkeypatch.setattr(AsyncClient, "get", mock_get_response)
    with pytest.raises(MeilisearchTaskFailedError):
        await async_wait_for_task(index.http_client, response.task_uid, raise_for_status=True)
