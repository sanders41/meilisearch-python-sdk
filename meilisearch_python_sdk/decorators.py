from __future__ import annotations

import asyncio
from functools import wraps
from typing import Any, Callable, NamedTuple

from meilisearch_python_sdk import AsyncClient, Client
from meilisearch_python_sdk._utils import use_task_groups


class ConnectionInfo(NamedTuple):
    """Infomation on how to connect to Meilisearch.

    url: URL for the Meilisearch server.
    api_key: The API key for the server.
    """

    url: str
    api_key: str


def async_add_documents(
    *,
    index_name: str,
    connection_info: AsyncClient | ConnectionInfo,
    batch_size: int | None = None,
    primary_key: str | None = None,
    wait_for_task: bool = False,
) -> Callable:
    """Decorator that takes the returned documents from a function and asyncronously adds them to Meilisearch.

    It is required that either an async_client or url is provided.

    Args:

        index_name: The name of the index to which the documents should be added.
        connection_info: Either an AsyncClient instance ConnectionInfo with informtaion on how to
            connect to Meilisearch.
        batch_size: If provided the documents will be sent in batches of the specified size.
            Otherwise all documents are sent at once. Default = None.
        primary_key: The primary key of the documents. This will be ignored if already set.
            Defaults to None.
        wait_for_task: If set to `True` the decorator will wait for the document addition to finish
            indexing before returning, otherwise it will return right away. Default = False.

    Returns:

        The list of documents proviced by the decorated function.

    Raises:

        MeilisearchCommunicationError: If there was an error communicating with the server.
        MeilisearchApiError: If the Meilisearch API returned an error.
        ValueError: If neither an async_client nor an url is provided.

    Examples:

        >>> from meilisearch_python_sdk import AsyncClient
        >>> from meilisearch_python_sdk.decorators import async_add_documents, ConnectionInfo
        >>>
        >>>
        >>> # with `AsyncClient`
        >>> client = AsyncClient(url="http://localhost:7700", api_key="masterKey")
        >>> @async_add_documents(index_name="movies", connection_info=client)
        >>> async def my_function() -> list[dict[str, Any]]:
        >>>     return [{"id": 1, "title": "Test 1"}, {"id": 2, "title": "Test 2"}]
        >>>
        >>> # with `ConnectionInfo`
        >>> @async_add_documents(
                index_name="movies",
                connection_info=ConnectionInfo(url="http://localhost:7700", api_key="masterKey"),
            )
        >>> async def my_function() -> list[dict[str, Any]]:
        >>>     return [{"id": 1, "title": "Test 1"}, {"id": 2, "title": "Test 2"}]
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            if isinstance(connection_info, AsyncClient):
                await _async_add_documents(
                    connection_info,
                    index_name,
                    result,
                    batch_size,
                    primary_key,
                    wait_for_task,
                )
                return result

            async with AsyncClient(connection_info.url, connection_info.api_key) as client:
                await _async_add_documents(
                    client, index_name, result, batch_size, primary_key, wait_for_task
                )

            return result

        return wrapper

    return decorator


def add_documents(
    *,
    index_name: str,
    connection_info: Client | ConnectionInfo,
    batch_size: int | None = None,
    primary_key: str | None = None,
    wait_for_task: bool = False,
) -> Callable:
    """Decorator that takes the returned documents from a function and adds them to Meilisearch.

    It is required that either an client or url is provided.

    Args:

        index_name: The name of the index to which the documents should be added.
        connection_info: Either an Client instance ConnectionInfo with informtaion on how to
            connect to Meilisearch.
        batch_size: If provided the documents will be sent in batches of the specified size.
            Otherwise all documents are sent at once. Default = None.
        primary_key: The primary key of the documents. This will be ignored if already set.
            Defaults to None.
        wait_for_task: If set to `True` the decorator will wait for the document addition to finish
            indexing before returning, otherwise it will return right away. Default = False.

    Returns:

        The list of documents proviced by the decorated function.

    Raises:

        MeilisearchCommunicationError: If there was an error communicating with the server.
        MeilisearchApiError: If the Meilisearch API returned an error.
        ValueError: If neither an async_client nor an url is provided.

    Examples:

        >>> from meilisearch_python_sdk import Client
        >>> from meilisearch_python_sdk.decorators import add_documents, ConnectionInfo
        >>>
        >>>
        >>> # With `Client`
        >>> client = Client(url="http://localhost:7700", api_key="masterKey")
        >>> @add_documents(index_name="movies", connection_info=client)
        >>> def my_function() -> list[dict[str, Any]]:
        >>>     return [{"id": 1, "title": "Test 1"}, {"id": 2, "title": "Test 2"}]
        >>>
        >>> # With `ConnectionInfo`
        >>> @add_documents(
                index_name="movies",
                connection_info=ConnectionInfo(url="http://localhost:7700", api_key="masterKey"),
            )
        >>> def my_function() -> list[dict[str, Any]]:
        >>>     return [{"id": 1, "title": "Test 1"}, {"id": 2, "title": "Test 2"}]
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            if isinstance(connection_info, Client):
                _add_documents(
                    connection_info,
                    index_name,
                    result,
                    batch_size,
                    primary_key,
                    wait_for_task,
                )
                return result

            decorator_client = Client(url=connection_info.url, api_key=connection_info.api_key)
            _add_documents(
                decorator_client,
                index_name,
                result,
                batch_size,
                primary_key,
                wait_for_task,
            )

            return result

        return wrapper

    return decorator


async def _async_add_documents(
    async_client: AsyncClient,
    index_name: str,
    documents: Any,
    batch_size: int | None,
    primary_key: str | None,
    wait_for_task: bool,
) -> None:
    index = async_client.index(index_name)
    if not batch_size:
        task = await index.add_documents(documents, primary_key)
        if wait_for_task:
            await async_client.wait_for_task(task.task_uid, timeout_in_ms=None)
        return

    tasks = await index.add_documents_in_batches(
        documents, batch_size=batch_size, primary_key=primary_key
    )

    if wait_for_task:
        if not use_task_groups():
            waits = [async_client.wait_for_task(x.task_uid) for x in tasks]
            await asyncio.gather(*waits)
            return

        async with asyncio.TaskGroup() as tg:  # type: ignore[attr-defined]
            [tg.create_task(async_client.wait_for_task(x.task_uid)) for x in tasks]


def _add_documents(
    client: Client,
    index_name: str,
    documents: Any,
    batch_size: int | None,
    primary_key: str | None,
    wait_for_task: bool,
) -> None:
    index = client.index(index_name)
    if not batch_size:
        task = index.add_documents(documents, primary_key)
        if wait_for_task:
            client.wait_for_task(task.task_uid, timeout_in_ms=None)
        return

    tasks = index.add_documents_in_batches(
        documents, batch_size=batch_size, primary_key=primary_key
    )

    if wait_for_task:
        for task in tasks:
            client.wait_for_task(task.task_uid)
