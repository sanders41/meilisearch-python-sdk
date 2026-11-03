from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from httpx2 import AsyncClient as HttpxAsyncClient
from httpx2 import Client as HttpxClient

from meilisearch_python_sdk._http_requests import AsyncHttpRequests, HttpRequests
from meilisearch_python_sdk._utils import get_async_client, get_client, process_params
from meilisearch_python_sdk.errors import MeilisearchTaskFailedError, MeilisearchTimeoutError
from meilisearch_python_sdk.models.task import TaskInfo, TaskResult, TaskStatus

if TYPE_CHECKING:
    from meilisearch_python_sdk._client import AsyncClient, Client  # pragma: no cover
    from meilisearch_python_sdk.types import JsonHandler


async def async_cancel_tasks(
    client: HttpxAsyncClient | AsyncClient,
    *,
    json_handler: JsonHandler,
    uids: list[int] | None = None,
    index_uids: list[str] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_finished_at: datetime | None = None,
) -> TaskInfo:
    """Cancel a list of enqueued or processing tasks.

    Defaults to cancelling all tasks.

    Args:
        client: An httpx HttpxAsyncClient or meilisearch_python_sdk AsyncClient instance.
        uids: A list of task UIDs to cancel.
        index_uids: A list of index UIDs for which to cancel tasks.
        statuses: A list of statuses to cancel.
        types: A list of types to cancel.
        before_enqueued_at: Cancel tasks that were enqueued before the specified date time.
        after_enqueued_at: Cancel tasks that were enqueued after the specified date time.
        before_started_at: Cancel tasks that were started before the specified date time.
        after_finished_at: Cancel tasks that were finished after the specified date time.

    Returns:
        The details of the task

    Raises:
        MeilisearchCommunicationError: If there was an error communicating with the server.
        MeilisearchApiError: If the Meilisearch API returned an error.
        MeilisearchTimeoutError: If the connection times out.

    Examples:
        >>> from meilisearch_python_sdk import AsyncClient
        >>> from meilisearch_python_sdk.task import cancel_tasks
        >>>
        >>> async with AsyncClient("http://localhost.com", "masterKey") as client:
        >>>     await cancel_tasks(client, uids=[1, 2])
    """
    parameters = process_params(
        uids=uids,
        index_uids=index_uids,
        statuses=statuses,
        types=types,
        before_enqueued_at=before_enqueued_at,
        after_enqueued_at=after_enqueued_at,
        before_started_at=before_started_at,
        after_finished_at=after_finished_at,
    )

    if not parameters:
        # Cancel all tasks if no parameters provided
        parameters["statuses"] = "enqueued,processing"

    url = f"tasks/cancel?{urlencode(parameters)}"
    client_ = get_async_client(client)
    http_requests = AsyncHttpRequests(client_, json_handler)
    response = await http_requests.post(url)

    return TaskInfo(**json_handler.loads(response.content))


async def async_delete_tasks(
    client: HttpxAsyncClient | AsyncClient,
    *,
    json_handler: JsonHandler,
    uids: list[int] | None = None,
    index_uids: list[str] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_finished_at: datetime | None = None,
) -> TaskInfo:
    parameters = process_params(
        uids=uids,
        index_uids=index_uids,
        statuses=statuses,
        types=types,
        before_enqueued_at=before_enqueued_at,
        after_enqueued_at=after_enqueued_at,
        before_started_at=before_started_at,
        after_finished_at=after_finished_at,
    )

    if not parameters:
        # delete all tasks if no parameters provided
        parameters["statuses"] = "canceled,enqueued,failed,processing,succeeded"

    url = f"tasks?{urlencode(parameters)}"
    client_ = get_async_client(client)
    http_requests = AsyncHttpRequests(client_, json_handler)
    response = await http_requests.delete(url)

    return TaskInfo(**json_handler.loads(response.content))


async def async_get_task(
    client: HttpxAsyncClient | AsyncClient,
    json_handler: JsonHandler,
    task_id: int,
) -> TaskResult:
    client_ = get_async_client(client)
    http_requests = AsyncHttpRequests(client_, json_handler)
    response = await http_requests.get(f"tasks/{task_id}")

    return TaskResult(**json_handler.loads(response.content))


async def async_get_tasks(
    client: HttpxAsyncClient | AsyncClient,
    *,
    json_handler: JsonHandler,
    index_ids: list[str] | None = None,
    types: str | list[str] | None = None,
    reverse: bool | None = None,
    uids: list[int] | None = None,
    batch_uids: list[int] | None = None,
    canceled_by: list[int] | None = None,
    statuses: str | list[str] | None = None,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_started_at: datetime | None = None,
    before_finished_at: datetime | None = None,
    after_finished_at: datetime | None = None,
    limit: int | None = None,
    from_: int | None = None,
) -> TaskStatus:
    parameters = process_params(
        uids=uids,
        index_uids=index_ids,
        statuses=statuses,
        types=types,
        before_enqueued_at=before_enqueued_at,
        after_enqueued_at=after_enqueued_at,
        before_started_at=before_started_at,
        after_finished_at=after_finished_at,
        batch_uids=batch_uids,
        canceled_by=canceled_by,
        after_started_at=after_started_at,
        before_finished_at=before_finished_at,
        limit=limit,
        from_=from_,
        reverse=reverse,
    )
    url = f"tasks?{urlencode(parameters)}" if parameters else "tasks"
    client_ = get_async_client(client)
    http_requests = AsyncHttpRequests(client_, json_handler)
    response = await http_requests.get(url)

    return TaskStatus(**json_handler.loads(response.content))


async def async_wait_for_task(
    client: HttpxAsyncClient | AsyncClient,
    task_id: int,
    *,
    json_handler: JsonHandler,
    timeout_in_ms: int | None = 5000,
    interval_in_ms: int = 50,
    raise_for_status: bool = False,
) -> TaskResult:
    client_ = get_async_client(client)
    http_requests = AsyncHttpRequests(client_, json_handler)
    url = f"tasks/{task_id}"
    start_time = time.monotonic()
    elapsed_time = 0.0

    while timeout_in_ms is None or elapsed_time < timeout_in_ms:
        response = await http_requests.get(url)
        status = TaskResult(**json_handler.loads(response.content))
        if status.status in ("succeeded", "failed", "canceled"):
            if raise_for_status and status.status == "failed":
                raise MeilisearchTaskFailedError(f"Task {task_id} failed")
            return status
        await asyncio.sleep(interval_in_ms / 1000)
        elapsed_time = (time.monotonic() - start_time) * 1000
    raise MeilisearchTimeoutError(
        f"timeout of {timeout_in_ms}ms has exceeded on process {task_id} when waiting for pending update to resolve."
    )


def cancel_tasks(
    client: HttpxClient | Client,
    *,
    json_handler: JsonHandler,
    uids: list[int] | None = None,
    index_uids: list[str] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_finished_at: datetime | None = None,
) -> TaskInfo:
    parameters = process_params(
        uids=uids,
        index_uids=index_uids,
        statuses=statuses,
        types=types,
        before_enqueued_at=before_enqueued_at,
        after_enqueued_at=after_enqueued_at,
        before_started_at=before_started_at,
        after_finished_at=after_finished_at,
    )

    if not parameters:
        # Cancel all tasks if no parameters provided
        parameters["statuses"] = "enqueued,processing"

    url = f"tasks/cancel?{urlencode(parameters)}"
    client_ = get_client(client)
    http_requests = HttpRequests(client_, json_handler)
    response = http_requests.post(url)

    return TaskInfo(**json_handler.loads(response.content))


def delete_tasks(
    client: HttpxClient | Client,
    *,
    json_handler: JsonHandler,
    uids: list[int] | None = None,
    index_uids: list[str] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_finished_at: datetime | None = None,
) -> TaskInfo:
    parameters = process_params(
        uids=uids,
        index_uids=index_uids,
        statuses=statuses,
        types=types,
        before_enqueued_at=before_enqueued_at,
        after_enqueued_at=after_enqueued_at,
        before_started_at=before_started_at,
        after_finished_at=after_finished_at,
    )

    if not parameters:
        # delete all tasks if no parameters provided
        parameters["statuses"] = "canceled,enqueued,failed,processing,succeeded"

    url = f"tasks?{urlencode(parameters)}"
    client_ = get_client(client)
    http_requests = HttpRequests(client_, json_handler)
    response = http_requests.delete(url)

    return TaskInfo(**json_handler.loads(response.content))


def get_task(client: HttpxClient | Client, json_handler: JsonHandler, task_id: int) -> TaskResult:
    client_ = get_client(client)
    http_requests = HttpRequests(client_, json_handler)
    response = http_requests.get(f"tasks/{task_id}")

    return TaskResult(**json_handler.loads(response.content))


def get_tasks(
    client: HttpxClient | Client,
    *,
    json_handler: JsonHandler,
    index_ids: list[str] | None = None,
    types: str | list[str] | None = None,
    reverse: bool | None = None,
    uids: list[int] | None = None,
    batch_uids: list[int] | None = None,
    canceled_by: list[int] | None = None,
    statuses: str | list[str] | None = None,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_started_at: datetime | None = None,
    before_finished_at: datetime | None = None,
    after_finished_at: datetime | None = None,
    limit: int | None = None,
    from_: int | None = None,
) -> TaskStatus:
    parameters = process_params(
        uids=uids,
        index_uids=index_ids,
        statuses=statuses,
        types=types,
        before_enqueued_at=before_enqueued_at,
        after_enqueued_at=after_enqueued_at,
        before_started_at=before_started_at,
        after_finished_at=after_finished_at,
        batch_uids=batch_uids,
        canceled_by=canceled_by,
        after_started_at=after_started_at,
        before_finished_at=before_finished_at,
        limit=limit,
        from_=from_,
        reverse=reverse,
    )
    url = f"tasks?{urlencode(parameters)}" if parameters else "tasks"
    client_ = get_client(client)
    http_requests = HttpRequests(client_, json_handler)
    response = http_requests.get(url)

    return TaskStatus(**json_handler.loads(response.content))


def wait_for_task(
    client: HttpxClient | Client,
    task_id: int,
    *,
    json_handler: JsonHandler,
    timeout_in_ms: int | None = 5000,
    interval_in_ms: int = 50,
    raise_for_status: bool = False,
) -> TaskResult:
    client_ = get_client(client)
    http_requests = HttpRequests(client_, json_handler=json_handler)
    url = f"tasks/{task_id}"
    start_time = time.monotonic()
    elapsed_time = 0.0

    while timeout_in_ms is None or elapsed_time < timeout_in_ms:
        response = http_requests.get(url)
        status = TaskResult(**json_handler.loads(response.content))
        if status.status in ("succeeded", "failed", "canceled"):
            if raise_for_status and status.status == "failed":
                raise MeilisearchTaskFailedError(f"Task {task_id} failed")
            return status
        time.sleep(interval_in_ms / 1000)
        elapsed_time = (time.monotonic() - start_time) * 1000
    raise MeilisearchTimeoutError(
        f"timeout of {timeout_in_ms}ms has exceeded on process {task_id} when waiting for pending update to resolve."
    )
