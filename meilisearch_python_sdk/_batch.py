from __future__ import annotations

from typing import TYPE_CHECKING

from meilisearch_python_sdk._utils import get_async_client
from meilisearch_python_sdk.models.batch import BatchResult, BatchStatus

if TYPE_CHECKING:
    from httpx import AsyncClient as HttpxAsyncClient  # pragma: no cover
    from httpx import Client as HttpxClient  # pragma: no cover

    from meilisearch_python_sdk._client import (  # pragma: no cover
        AsyncClient,
        Client,
    )


async def async_get_batch(
    client: HttpxAsyncClient | AsyncClient, batch_uid: str
) -> BatchResult | None:
    client_ = get_async_client(client)
    response = await client_.get(f"batches/{batch_uid}")
    if not response.json():
        return None

    return BatchResult(**response.json())


async def async_get_batches(client: HttpxAsyncClient | AsyncClient) -> BatchStatus:
    client_ = get_async_client(client)
    response = await client_.get("batches")

    return BatchStatus(**response.json())


def get_batch(client: HttpxClient | Client, batch_uid: str) -> BatchResult | None:
    client_ = get_async_client(client)
    response = client_.get(f"batches/{batch_uid}")
    if not response.json():
        return None

    return BatchResult(**response.json())


def get_batches(client: HttpxClient | Client) -> BatchStatus:
    client_ = get_async_client(client)
    response = client_.get("batches")

    return BatchStatus(**response.json())
