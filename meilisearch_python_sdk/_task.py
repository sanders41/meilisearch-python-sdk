from __future__ import annotations

import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from httpx import AsyncClient as HttpxAsyncClient
from httpx import Client as HttpxClient

from meilisearch_python_sdk._http_requests import AsyncHttpRequests, HttpRequests
from meilisearch_python_sdk.errors import MeilisearchTaskFailedError, MeilisearchTimeoutError
from meilisearch_python_sdk.models.task import TaskInfo, TaskResult, TaskStatus

if TYPE_CHECKING:
    from meilisearch_python_sdk._client import AsyncClient, Client  # pragma: no cover


async def async_cancel_tasks(
    client: HttpxAsyncClient | AsyncClient,
    *,
    uids: list[str] | None = None,
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
    parameters = _process_params(
        uids,
        index_uids,
        statuses,
        types,
        before_enqueued_at,
        after_enqueued_at,
        before_started_at,
        after_finished_at,
    )

    if not parameters:
        # Cancel all tasks if no parmaeters provided
        parameters["statuses"] = "enqueued,processing"

    url = f"tasks/cancel?{urlencode(parameters)}"
    client_ = _get_async_client(client)
    response = await client_.post(url)

    return TaskInfo(**response.json())


async def async_delete_tasks(
    client: HttpxAsyncClient | AsyncClient,
    *,
    uids: list[str] | None = None,
    index_uids: list[str] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_finished_at: datetime | None = None,
) -> TaskInfo:
    parameters = _process_params(
        uids,
        index_uids,
        statuses,
        types,
        before_enqueued_at,
        after_enqueued_at,
        before_started_at,
        after_finished_at,
    )

    if not parameters:
        # delete all tasks if no parmaeters provided
        parameters["statuses"] = "canceled,enqueued,failed,processing,succeeded"

    url = f"tasks?{urlencode(parameters)}"
    client_ = _get_async_client(client)
    response = await client_.delete(url)

    return TaskInfo(**response.json())


async def async_get_task(client: HttpxAsyncClient | AsyncClient, task_id: int) -> TaskResult:
    client_ = _get_async_client(client)
    response = await client_.get(f"tasks/{task_id}")

    return TaskResult(**response.json())


async def async_get_tasks(
    client: HttpxAsyncClient | AsyncClient,
    *,
    index_ids: list[str] | None = None,
    types: str | list[str] | None = None,
) -> TaskStatus:
    url = f"tasks?indexUids={','.join(index_ids)}" if index_ids else "tasks"
    if types:
        formatted_types = ",".join(types) if isinstance(types, list) else types
        url = f"{url}&types={formatted_types}" if "?" in url else f"{url}?types={formatted_types}"
    client_ = _get_async_client(client)
    response = await client_.get(url)

    return TaskStatus(**response.json())


async def async_wait_for_task(
    client: HttpxAsyncClient | AsyncClient,
    task_id: int,
    *,
    timeout_in_ms: int | None = 5000,
    interval_in_ms: int = 50,
    raise_for_status: bool = False,
) -> TaskResult:
    client_ = _get_async_client(client)
    url = f"tasks/{task_id}"
    http_requests = AsyncHttpRequests(client_)
    start_time = datetime.now()
    elapsed_time = 0.0

    if timeout_in_ms:
        while elapsed_time < timeout_in_ms:
            response = await http_requests.get(url)
            status = TaskResult(**response.json())
            if status.status in ("succeeded", "failed"):
                if raise_for_status and status.status == "failed":
                    raise MeilisearchTaskFailedError(f"Task {task_id} failed")
                return status
            await asyncio.sleep(interval_in_ms / 1000)
            time_delta = datetime.now() - start_time
            elapsed_time = time_delta.seconds * 1000 + time_delta.microseconds / 1000
        raise MeilisearchTimeoutError(
            f"timeout of {timeout_in_ms}ms has exceeded on process {task_id} when waiting for pending update to resolve."
        )
    else:
        while True:
            response = await http_requests.get(url)
            status = TaskResult(**response.json())
            if status.status in ("succeeded", "failed"):
                if raise_for_status and status.status == "failed":
                    raise MeilisearchTaskFailedError(f"Task {task_id} failed")
                return status
            await asyncio.sleep(interval_in_ms / 1000)


def cancel_tasks(
    client: HttpxClient | Client,
    *,
    uids: list[str] | None = None,
    index_uids: list[str] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_finished_at: datetime | None = None,
) -> TaskInfo:
    parameters = _process_params(
        uids,
        index_uids,
        statuses,
        types,
        before_enqueued_at,
        after_enqueued_at,
        before_started_at,
        after_finished_at,
    )

    if not parameters:
        # Cancel all tasks if no parmaeters provided
        parameters["statuses"] = "enqueued,processing"

    url = f"tasks/cancel?{urlencode(parameters)}"
    client_ = _get_client(client)
    response = client_.post(url)

    return TaskInfo(**response.json())


def delete_tasks(
    client: HttpxClient | Client,
    *,
    uids: list[str] | None = None,
    index_uids: list[str] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_finished_at: datetime | None = None,
) -> TaskInfo:
    parameters = _process_params(
        uids,
        index_uids,
        statuses,
        types,
        before_enqueued_at,
        after_enqueued_at,
        before_started_at,
        after_finished_at,
    )

    if not parameters:
        # delete all tasks if no parmaeters provided
        parameters["statuses"] = "canceled,enqueued,failed,processing,succeeded"

    url = f"tasks?{urlencode(parameters)}"
    client_ = _get_client(client)
    response = client_.delete(url)

    return TaskInfo(**response.json())


def get_task(client: HttpxClient | Client, task_id: int) -> TaskResult:
    client_ = _get_client(client)
    response = client_.get(f"tasks/{task_id}")

    return TaskResult(**response.json())


def get_tasks(
    client: HttpxClient | Client,
    *,
    index_ids: list[str] | None = None,
    types: str | list[str] | None = None,
) -> TaskStatus:
    url = f"tasks?indexUids={','.join(index_ids)}" if index_ids else "tasks"
    if types:
        formatted_types = ",".join(types) if isinstance(types, list) else types
        url = f"{url}&types={formatted_types}" if "?" in url else f"{url}?types={formatted_types}"
    client_ = _get_client(client)
    response = client_.get(url)

    return TaskStatus(**response.json())


def wait_for_task(
    client: HttpxClient | Client,
    task_id: int,
    *,
    timeout_in_ms: int | None = 5000,
    interval_in_ms: int = 50,
    raise_for_status: bool = False,
) -> TaskResult:
    client_ = _get_client(client)
    url = f"tasks/{task_id}"
    http_requests = HttpRequests(client_)
    start_time = datetime.now()
    elapsed_time = 0.0

    if timeout_in_ms:
        while elapsed_time < timeout_in_ms:
            response = http_requests.get(url)
            status = TaskResult(**response.json())
            if status.status in ("succeeded", "failed"):
                if raise_for_status and status.status == "failed":
                    raise MeilisearchTaskFailedError(f"Task {task_id} failed")
                return status
            time.sleep(interval_in_ms / 1000)
            time_delta = datetime.now() - start_time
            elapsed_time = time_delta.seconds * 1000 + time_delta.microseconds / 1000
        raise MeilisearchTimeoutError(
            f"timeout of {timeout_in_ms}ms has exceeded on process {task_id} when waiting for pending update to resolve."
        )
    else:
        while True:
            response = http_requests.get(url)
            status = TaskResult(**response.json())
            if status.status in ("succeeded", "failed"):
                if raise_for_status and status.status == "failed":
                    raise MeilisearchTaskFailedError(f"Task {task_id} failed")
                return status
            time.sleep(interval_in_ms / 1000)


def _get_async_client(client: AsyncClient | HttpxAsyncClient) -> HttpxAsyncClient:
    if isinstance(client, HttpxAsyncClient):
        return client

    return client.http_client


def _get_client(
    client: Client | HttpxClient,
) -> HttpxClient:
    if isinstance(client, HttpxClient):
        return client

    return client.http_client


def _process_params(
    uids: list[str] | None = None,
    index_uids: list[str] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_finished_at: datetime | None = None,
) -> dict[str, str]:
    parameters = {}
    if uids:
        parameters["uids"] = ",".join([str(x) for x in uids])
    if index_uids:
        parameters["indexUids"] = ",".join([str(x) for x in index_uids])
    if statuses:
        parameters["statuses"] = ",".join(statuses)
    if types:
        parameters["types"] = ",".join(types)
    if before_enqueued_at:
        parameters["beforeEnqueuedAt"] = f"{before_enqueued_at.isoformat()}Z"
    if after_enqueued_at:
        parameters["afterEnqueuedAt"] = f"{after_enqueued_at.isoformat()}Z"
    if before_started_at:
        parameters["beforeStartedAt"] = f"{before_started_at.isoformat()}Z"
    if after_finished_at:
        parameters["afterFinishedAt"] = f"{after_finished_at.isoformat()}Z"

    return parameters
