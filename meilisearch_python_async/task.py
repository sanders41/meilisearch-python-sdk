from __future__ import annotations

from asyncio import sleep
from datetime import datetime

from httpx import AsyncClient

from meilisearch_python_async._http_requests import HttpRequests
from meilisearch_python_async.errors import MeiliSearchTimeoutError
from meilisearch_python_async.models.task import TaskStatus


async def get_tasks(http_client: AsyncClient, index_id: str | None = None) -> list[TaskStatus]:
    """Get all tasks.

    Args:

        http_client: An AsyncClient instance.
        index_id: The id of the index for which to get the tasks. If provided this will get the
            tasks only for the specified index, if not all tasks will be returned. Default = None

    Returns:

        A list of all tasks.

    Raises:

        MeilisearchCommunicationError: If there was an error communicating with the server.
        MeilisearchApiError: If the MeiliSearch API returned an error.
        MeiliSearchTimeoutError: If the connection times out.

    Examples:

        >>> from meilisearch_python_async import Client
        >>> from meilisearch_python_async.task import get_tasks
        >>>
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     await get_tasks(client.http_client)
    """
    url = f"tasks?indexUid={index_id}" if index_id else "tasks"
    response = await http_client.get(url)
    tasks = [TaskStatus(**x) for x in response.json()["results"]]

    return tasks


async def get_task(http_client: AsyncClient, task_id: int) -> TaskStatus:
    """Get a single task from it's task id.

    Args:

        http_client: An AsyncClient instance.
        task_id: Identifier of the task to retrieve.

    Returns:

        A list of all tasks.

    Raises:

        MeilisearchCommunicationError: If there was an error communicating with the server.
        MeilisearchApiError: If the MeiliSearch API returned an error.
        MeiliSearchTimeoutError: If the connection times out.

    Examples:

        >>> from meilisearch_python_async import Client
        >>> from meilisearch_python_async.task import get_task
        >>>
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     await get_task(client.http_client, 1244)
    """
    response = await http_client.get(f"tasks/{task_id}")

    return TaskStatus(**response.json())


async def wait_for_task(
    http_client: AsyncClient, task_id: int, *, timeout_in_ms: int = 5000, interval_in_ms: int = 50
) -> TaskStatus:
    """Wait until MeiliSearch processes a task, and get its status.

    Args:

        http_client: An AsyncClient instance.
        task_id: Identifier of the task to retrieve.
        timeout_in_ms: Amount of time in milliseconds to wait before raising a
            MeiliSearchTimeoutError. Defaults to 5000.
        interval_in_ms: Time interval in miliseconds to sleep between requests. Defaults to 50.

    Returns:

        Details of the processed update status.

    Raises:

        MeilisearchCommunicationError: If there was an error communicating with the server.
        MeilisearchApiError: If the MeiliSearch API returned an error.
        MeiliSearchTimeoutError: If the connection times out.

    Examples:

        >>> from meilisearch_python_async import Client
        >>> from meilisearch_python_async.task import wait_for_task
        >>> >>> documents = [
        >>>     {"id": 1, "title": "Movie 1", "genre": "comedy"},
        >>>     {"id": 2, "title": "Movie 2", "genre": "drama"},
        >>> ]
        >>> async with Client("http://localhost.com", "masterKey") as client:
        >>>     index = client.index("movies")
        >>>     response = await index.add_documents(documents)
        >>>     await wait_for_pending_task(client.http_client, response.update_id)
    """
    url = f"tasks/{task_id}"
    http_requests = HttpRequests(http_client)
    start_time = datetime.now()
    elapsed_time = 0.0
    while elapsed_time < timeout_in_ms:
        response = await http_requests.get(url)
        status = TaskStatus(**response.json())
        if status.status in ("succeeded", "failed"):
            return status
        await sleep(interval_in_ms / 1000)
        time_delta = datetime.now() - start_time
        elapsed_time = time_delta.seconds * 1000 + time_delta.microseconds / 1000
    raise MeiliSearchTimeoutError(
        f"timeout of {timeout_in_ms}ms has exceeded on process {task_id} when waiting for pending update to resolve."
    )
