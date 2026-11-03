from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from meilisearch_python_sdk._http_requests import AsyncHttpRequests, HttpRequests
from meilisearch_python_sdk._utils import get_async_client, get_client, process_params
from meilisearch_python_sdk.errors import BatchNotFoundError, MeilisearchApiError
from meilisearch_python_sdk.models.batch import BatchResult, BatchStatus

if TYPE_CHECKING:
    from httpx2 import AsyncClient as HttpxAsyncClient  # pragma: no cover
    from httpx2 import Client as HttpxClient  # pragma: no cover

    from meilisearch_python_sdk._client import (  # pragma: no cover
        AsyncClient,
        Client,
    )
    from meilisearch_python_sdk.types import JsonHandler


async def async_get_batch(
    client: HttpxAsyncClient | AsyncClient, json_handler: JsonHandler, batch_uid: int
) -> BatchResult:
    client_ = get_async_client(client)
    http_requests = AsyncHttpRequests(client_, json_handler)
    try:
        response = await http_requests.get(f"batches/{batch_uid}")
    except MeilisearchApiError as e:
        if e.status_code == 404:
            raise BatchNotFoundError(f"Batch {batch_uid} not found") from e
        raise  # pragma: no cover

    return BatchResult(**json_handler.loads(response.content))


async def async_get_batches(
    client: HttpxAsyncClient | AsyncClient,
    *,
    json_handler: JsonHandler,
    uids: list[int] | None = None,
    batch_uids: list[int] | None = None,
    index_uids: list[str] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    limit: int = 20,
    from_: str | None = None,
    reverse: bool = False,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_finished_at: datetime | None = None,
) -> BatchStatus:
    client_ = get_async_client(client)
    http_requests = AsyncHttpRequests(client_, json_handler)
    params = process_params(
        uids=uids,
        batch_uids=batch_uids,
        index_uids=index_uids,
        statuses=statuses,
        types=types,
        limit=limit,
        from_=from_,
        reverse=reverse,
        before_enqueued_at=before_enqueued_at,
        after_enqueued_at=after_enqueued_at,
        before_started_at=before_started_at,
        after_finished_at=after_finished_at,
    )
    response = await http_requests.get(f"batches?{urlencode(params)}")

    return BatchStatus(**json_handler.loads(response.content))


def get_batch(
    client: HttpxClient | Client, json_handler: JsonHandler, batch_uid: int
) -> BatchResult:
    client_ = get_client(client)
    http_requests = HttpRequests(client_, json_handler)
    try:
        response = http_requests.get(f"batches/{batch_uid}")
    except MeilisearchApiError as e:
        if e.status_code == 404:
            raise BatchNotFoundError(f"Batch {batch_uid} not found") from e
        raise  # pragma: no cover

    return BatchResult(**json_handler.loads(response.content))


def get_batches(
    client: HttpxClient | Client,
    *,
    json_handler: JsonHandler,
    uids: list[int] | None = None,
    batch_uids: list[int] | None = None,
    index_uids: list[str] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    limit: int = 20,
    from_: str | None = None,
    reverse: bool = False,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_finished_at: datetime | None = None,
) -> BatchStatus:
    client_ = get_client(client)
    http_requests = HttpRequests(client_, json_handler)
    params = process_params(
        uids=uids,
        batch_uids=batch_uids,
        index_uids=index_uids,
        statuses=statuses,
        types=types,
        limit=limit,
        from_=from_,
        reverse=reverse,
        before_enqueued_at=before_enqueued_at,
        after_enqueued_at=after_enqueued_at,
        before_started_at=before_started_at,
        after_finished_at=after_finished_at,
    )

    response = http_requests.get(f"batches?{urlencode(params)}")

    return BatchStatus(**json_handler.loads(response.content))
