from __future__ import annotations

from datetime import datetime
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


async def async_get_batches(
    client: HttpxAsyncClient | AsyncClient,
    *,
    uids: list[int] | None = None,
    batch_uids: list[int] | None = None,
    index_uids: list[int] | None = None,
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
    params = _build_parameters(
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
    response = await client_.get("batches", params=params)

    return BatchStatus(**response.json())


def get_batch(client: HttpxClient | Client, batch_uid: int) -> BatchResult | None:
    client_ = get_client(client)
    response = client_.get(f"batches/{batch_uid}")

    if response.status_code == 404:
        raise BatchNotFoundError(f"Batch {batch_uid} not found")

    return BatchResult(**response.json())


def get_batches(
    client: HttpxClient | Client,
    *,
    uids: list[int] | None = None,
    batch_uids: list[int] | None = None,
    index_uids: list[int] | None = None,
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
    params = _build_parameters(
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

    response = client_.get("batches", params=params)

    return BatchStatus(**response.json())


def _build_parameters(
    *,
    uids: list[int] | None = None,
    batch_uids: list[int] | None = None,
    index_uids: list[int] | None = None,
    statuses: list[str] | None = None,
    types: list[str] | None = None,
    limit: int = 20,
    from_: str | None = None,
    reverse: bool = False,
    before_enqueued_at: datetime | None = None,
    after_enqueued_at: datetime | None = None,
    before_started_at: datetime | None = None,
    after_finished_at: datetime | None = None,
) -> dict[str, str]:
    params = {}

    if uids:
        params["uids"] = ",".join([str(uid) for uid in uids])

    if batch_uids:  # pragma: no cover
        params["batchUids"] = ",".join([str(uid) for uid in batch_uids])

    if index_uids:  # pragma: no cover
        params["indexUids"] = ",".join([str(uid) for uid in index_uids])

    if statuses:  # pragma: no cover
        params["statuses"] = ",".join(statuses)

    if types:  # pragma: no cover
        params["types"] = ",".join(types)

    params["limit"] = str(limit)

    if from_:  # pragma: no cover
        params["from"] = from_

    params["reverse"] = "true" if reverse else "false"

    if before_enqueued_at:  # pragma: no cover
        params["beforeEnqueuedAt"] = before_enqueued_at.isoformat()

    if after_enqueued_at:  # pragma: no cover
        params["afterEnqueuedAt"] = after_enqueued_at.isoformat()

    if before_started_at:  # pragma: no cover
        params["beforeStartedAt"] = before_started_at.isoformat()

    if after_finished_at:  # pragma: no cover
        params["afterFinishedAt"] = after_finished_at.isoformat()

    return params
