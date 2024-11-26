from __future__ import annotations

from typing import TYPE_CHECKING

from meilisearch_python_sdk._utils import get_async_client, get_client
from meilisearch_python_sdk.errors import BatchNotFoundError
from meilisearch_python_sdk.models.batch import BatchResult, BatchStatus

if TYPE_CHECKING:
    from httpx import AsyncClient as HttpxAsyncClient  # pragma: no cover
    from httpx import Client as HttpxClient  # pragma: no cover

    from meilisearch_python_sdk._client import (  # pragma: no cover
        AsyncClient,
        Client,
    )


async def async_get_batch(
    client: HttpxAsyncClient | AsyncClient, batch_uid: int
) -> BatchResult | None:
    client_ = get_async_client(client)
    response = await client_.get(f"batches/{batch_uid}")

    if response.status_code == 404:
        raise BatchNotFoundError(f"Batch {batch_uid} not found")

    return BatchResult(**response.json())


async def async_get_batches(client: HttpxAsyncClient | AsyncClient) -> BatchStatus:
    client_ = get_async_client(client)
    response = await client_.get("batches")

    return BatchStatus(**response.json())


def get_batch(client: HttpxClient | Client, batch_uid: int) -> BatchResult | None:
    client_ = get_client(client)
    response = client_.get(f"batches/{batch_uid}")

    if response.status_code == 404:
        raise BatchNotFoundError(f"Batch {batch_uid} not found")

    return BatchResult(**response.json())


def get_batches(client: HttpxClient | Client) -> BatchStatus:
    client_ = get_client(client)
    response = client_.get("batches")

    return BatchStatus(**response.json())
